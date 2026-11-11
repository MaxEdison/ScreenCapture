"""Low-latency WebSocket / MJPEG server.

  * Frames go out over a WebSocket with TCP_NODELAY and a tiny in-flight window (the viewer
    ACKs every frame). A slow viewer never builds a queue: it always receives the NEWEST frame.
  * Every viewer may ask for its own maximum width (a phone does not need 1080p), so weak
    devices get smaller frames while a laptop on the same stream still gets full quality.
  * The mouse cursor is sent separately (tiny messages at ~90 Hz) and drawn by the viewer.
"""

import asyncio
import json
import socket
import threading
import time
from pathlib import Path

from aiohttp import WSMsgType, web

from .capture import Capturer
from .system import get_cursor_pos

WEB_DIR = Path(__file__).resolve().parent / "web"
MAX_IN_FLIGHT = 2          # frames sent but not yet ACKed by a viewer
CURSOR_HZ = 90
ALLOWED_WIDTHS = {0, 640, 960, 1280, 1600, 1920, 2560}


class Client:
    def __init__(self, ip=""):
        self.ip = ip
        self.wake = asyncio.Event()
        self.inflight = 0
        self.width = 0           # viewer-requested max width (0 = host default)
        self.frame_seq = 0
        self.cursor_seq = 0
        self.status_seq = -1
        self.last_send = 0.0
        self.lock = asyncio.Lock()


class ScreenServer:
    def __init__(self, settings):
        self.settings = settings
        self.clients = set()
        self.frames = {}           # latest {width: header+JPEG payload}
        self.frame_seq = 0
        self.cursor_seq = 0
        self.cursor_msg = ""
        self._cursor_key = None
        self.status_seq = 0
        self.paused = False
        self.sent_bytes = 0
        self.sent_frames = 0
        self.capturer = None
        self._wss = set()
        self._stopping = False
        self._loop = None
        self._stop = None
        self._thread = None
        self._ready = threading.Event()
        self._error = None

    # ------------------------------------------------------------------ public API (GUI thread)
    def start(self):
        self._ready.clear()
        self._error = None
        self._thread = threading.Thread(target=self._run, daemon=True, name="server")
        self._thread.start()
        self._ready.wait(8)
        if self._error:
            raise self._error

    def stop(self):
        if self._loop and self._stop:
            self._loop.call_soon_threadsafe(self._stop.set)
        if self._thread:
            self._thread.join(6)

    def set_paused(self, paused):
        self.paused = paused
        if self._loop:
            self._loop.call_soon_threadsafe(self._bump_status)

    def stats(self):
        cap = self.capturer
        return {
            "clients": len(self.clients),
            "devices": sorted({c.ip for c in tuple(self.clients) if c.ip}),
            "bytes": self.sent_bytes,
            "frames": self.sent_frames,
            "encode_ms": cap.encode_ms if cap else 0.0,
            "backend": cap.backend if cap else "",
        }

    # ------------------------------------------------------------------ internals
    def _run(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        try:
            self._loop.run_until_complete(self._serve())
        except Exception as exc:  # port busy, etc.
            self._error = exc
            self._ready.set()
        finally:
            self._loop.close()

    async def _serve(self):
        self._stop = asyncio.Event()
        app = web.Application()
        app.add_routes([
            web.get("/", self._index),
            web.get("/ws", self._ws),
            web.get("/stream", self._mjpeg),
            web.get("/info", self._info),
            web.get("/check", self._check),
            web.static("/fonts", WEB_DIR / "fonts"),
        ])
        runner = web.AppRunner(app, access_log=None, shutdown_timeout=1.0)
        await runner.setup()
        await web.TCPSite(runner, "0.0.0.0", self.settings.port, backlog=64).start()

        self.capturer = Capturer(self.settings, lambda: bool(self.clients), self._wanted_widths,
                                 lambda: self.paused, self._publish)
        self.capturer.start()
        cursor_task = asyncio.create_task(self._cursor_loop())
        self._ready.set()
        try:
            await self._stop.wait()
        finally:
            self._stopping = True
            cursor_task.cancel()
            for c in tuple(self.clients):
                c.wake.set()
            await asyncio.gather(*(ws.close(code=1001) for ws in tuple(self._wss)), return_exceptions=True)
            await asyncio.get_running_loop().run_in_executor(None, self.capturer.stop)
            await runner.cleanup()

    def _eff_width(self, c):
        host = self.settings.max_width
        if c.width == 0:
            return host
        return c.width if host == 0 else min(c.width, host)

    def _wanted_widths(self):
        return {self._eff_width(c) for c in tuple(self.clients)} or {self.settings.max_width}

    def _payload_for(self, c):
        frames = self.frames
        return frames.get(self._eff_width(c)) or next(iter(frames.values()))

    def _publish(self, payloads):
        self._loop.call_soon_threadsafe(self._set_frames, payloads)

    def _set_frames(self, payloads):
        self.frames = payloads
        self.frame_seq += 1
        for c in self.clients:
            c.wake.set()

    def _bump_status(self):
        self.status_seq += 1
        for c in self.clients:
            c.wake.set()

    async def _cursor_loop(self):
        while True:
            await asyncio.sleep(1.0 / CURSOR_HZ)
            mon = self.capturer.mon if self.capturer else None
            if not self.clients or mon is None:
                continue
            pos = get_cursor_pos()
            if pos is None:
                return
            fx = (pos[0] - mon["left"]) / max(1, mon["width"])
            fy = (pos[1] - mon["top"]) / max(1, mon["height"])
            visible = self.settings.show_cursor and 0 <= fx <= 1 and 0 <= fy <= 1
            key = (round(fx, 5), round(fy, 5), visible)
            if key != self._cursor_key:
                self._cursor_key = key
                self.cursor_msg = json.dumps({"t": "c", "x": key[0], "y": key[1], "v": int(visible)})
                self.cursor_seq += 1
                for c in self.clients:
                    c.wake.set()

    # ------------------------------------------------------------------ HTTP handlers
    def _pin_ok(self, request):
        pin = self.settings.pin
        return not pin or request.query.get("pin", "") == pin

    async def _index(self, request):
        try:
            return web.Response(body=(WEB_DIR / "viewer.html").read_bytes(), content_type="text/html",
                                charset="utf-8", headers={"Cache-Control": "no-store"})
        except OSError:
            return web.Response(status=500, text="viewer.html is missing")

    async def _info(self, request):
        return web.json_response({"pin_required": bool(self.settings.pin)})

    async def _check(self, request):
        return web.Response(status=200 if self._pin_ok(request) else 403)

    async def _ws(self, request):
        if not self._pin_ok(request):
            raise web.HTTPForbidden()
        ws = web.WebSocketResponse(max_msg_size=0, compress=False, heartbeat=10)
        await ws.prepare(request)
        try:
            request.transport.get_extra_info("socket").setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except Exception:
            pass

        client = Client(request.remote or "")
        self.clients.add(client)
        self._wss.add(ws)
        client.wake.set()
        sender = asyncio.create_task(self._send_loop(ws, client))
        try:
            async for msg in ws:
                if msg.type != WSMsgType.TEXT:
                    continue
                data = msg.data
                if data == "a":                                  # ACK: next frame may be sent
                    client.inflight = max(0, client.inflight - 1)
                    client.wake.set()
                elif data[0] == "p":                             # ping -> echo, for RTT display
                    async with client.lock:
                        await ws.send_str(data)
                elif data[0] == "w" and data[1:].isdigit():      # viewer asks for a max width
                    width = int(data[1:])
                    client.width = width if width in ALLOWED_WIDTHS else 0
                    client.frame_seq = 0                         # resend a frame at the new size
                    client.wake.set()
        finally:
            sender.cancel()
            self.clients.discard(client)
            self._wss.discard(ws)
        return ws

    async def _send_loop(self, ws, c):
        try:
            while not ws.closed:
                try:
                    await asyncio.wait_for(c.wake.wait(), 1.0)
                except asyncio.TimeoutError:
                    if c.inflight and time.monotonic() - c.last_send > 2.0:
                        c.inflight = 0          # viewer lost an ACK; do not stall forever
                c.wake.clear()
                if c.status_seq != self.status_seq:
                    c.status_seq = self.status_seq
                    async with c.lock:
                        await ws.send_str(json.dumps({"t": "s", "paused": int(self.paused)}))
                if c.cursor_seq != self.cursor_seq:
                    c.cursor_seq = self.cursor_seq
                    async with c.lock:
                        await ws.send_str(self.cursor_msg)
                if self.frames and c.frame_seq != self.frame_seq and c.inflight < MAX_IN_FLIGHT:
                    c.frame_seq = self.frame_seq
                    c.inflight += 1
                    c.last_send = time.monotonic()
                    payload = self._payload_for(c)
                    async with c.lock:
                        await ws.send_bytes(payload)
                    self.sent_bytes += len(payload)
                    self.sent_frames += 1
        except (asyncio.CancelledError, ConnectionResetError):
            pass

    async def _mjpeg(self, request):
        """Plain MJPEG fallback (works in any browser / <img> tag / VLC)."""
        if not self._pin_ok(request):
            raise web.HTTPForbidden()
        resp = web.StreamResponse(headers={
            "Content-Type": "multipart/x-mixed-replace; boundary=frame",
            "Cache-Control": "no-store",
        })
        await resp.prepare(request)
        client = Client(request.remote or "")
        self.clients.add(client)
        client.wake.set()
        try:
            while not self._stopping:
                try:
                    await asyncio.wait_for(client.wake.wait(), 2.0)
                except asyncio.TimeoutError:
                    pass
                client.wake.clear()
                if self.frames and client.frame_seq != self.frame_seq:
                    client.frame_seq = self.frame_seq
                    jpeg = self._payload_for(client)[8:]
                    await resp.write(b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                                     + str(len(jpeg)).encode() + b"\r\n\r\n" + jpeg + b"\r\n")
                    self.sent_bytes += len(jpeg)
                    self.sent_frames += 1
        except (asyncio.CancelledError, ConnectionResetError):
            pass
        finally:
            self.clients.discard(client)
        return resp
