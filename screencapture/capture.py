"""Screen grabbing + JPEG encoding.

Two pipelined threads: one grabs frames, one JPEG-encodes the NEWEST one. Old frames are
dropped instead of queued, so latency never builds up. Each frame is encoded once per
requested viewer width (usually one or two widths), then shared by all viewers.
"""

import io
import os
import struct
import threading
import time
import warnings
import zlib

from PIL import Image

from .system import MSS, timer_resolution

KEEPALIVE_SECONDS = 1.0    # re-send an unchanged screen at most this often

try:                       # optional: GPU (DXGI) capture on Windows
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        import dxcam as _dxcam
except Exception:
    _dxcam = None


class _Source:
    """Prefers DXGI desktop duplication (GPU, ~3x faster, reports unchanged screens for
    free) and falls back to GDI via mss."""

    def __init__(self):
        self.sct = None
        self.cam = None
        self.cam_idx = None
        self.use_dx = _dxcam is not None and os.name == "nt"
        self.mon = None
        self.backend = "mss"
        self._last = None
        self._crc = None
        self._last_t = 0.0

    def close(self):
        self._close_cam()
        if self.sct is not None:
            try:
                self.sct.close()
            except Exception:
                pass
            self.sct = None

    def _close_cam(self):
        if self.cam is not None:
            try:
                self.cam.release()
            except Exception:
                pass
        self.cam = self.cam_idx = None

    def reset(self):
        """Called while nobody is watching. Releasing the DXGI duplication guarantees the next
        grab returns the current screen even if nothing changes on it."""
        self._last = self._crc = None
        self._close_cam()

    def grab(self, monitor):
        """Return (size, BGRX buffer) for a changed (or keep-alive) frame, else None."""
        if self.sct is None:
            self.sct = MSS()
        mons = self.sct.monitors
        idx = monitor if 0 <= monitor < len(mons) else 1
        self.mon = mons[idx]
        now = time.perf_counter()
        keepalive = self._last is not None and now - self._last_t >= KEEPALIVE_SECONDS

        if self.use_dx and idx >= 1:
            try:
                if self.cam is None or self.cam_idx != idx:
                    self._close_cam()
                    self.cam = _dxcam.create(output_idx=idx - 1, output_color="BGRA")
                    self.cam_idx = idx
                frame = self.cam.grab()
                self.backend = "dxgi"
                if frame is None:
                    return self._touch(now) if keepalive else None
                self._last = ((frame.shape[1], frame.shape[0]), frame.copy())
                return self._touch(now)
            except Exception:
                self.use_dx = False
                self._close_cam()

        shot = self.sct.grab(self.mon)
        self.backend = "mss"
        crc = zlib.crc32(shot.bgra)
        if crc == self._crc and not keepalive:
            return None
        self._crc = crc
        self._last = (shot.size, shot.bgra)
        return self._touch(now)

    def _touch(self, now):
        self._last_t = now
        return self._last


class Capturer:
    def __init__(self, settings, has_clients, wanted_widths, is_paused, publish):
        self.settings = settings
        self.has_clients = has_clients
        self.wanted_widths = wanted_widths      # () -> set of max widths to encode (0 = native)
        self.is_paused = is_paused
        self.publish = publish                  # ({width: payload}) -> None
        self.stop_event = threading.Event()
        self.cond = threading.Condition()
        self.slot = None
        self.source = _Source()
        self.frames = 0
        self.encode_ms = 0.0
        self._threads = [threading.Thread(target=self._grab_loop, daemon=True, name="grab"),
                         threading.Thread(target=self._encode_loop, daemon=True, name="encode")]

    @property
    def mon(self):
        return self.source.mon

    @property
    def backend(self):
        return self.source.backend

    def start(self):
        for t in self._threads:
            t.start()

    def stop(self):
        self.stop_event.set()
        with self.cond:
            self.cond.notify_all()
        for t in self._threads:
            t.join(1.0)

    def _grab_loop(self):
        timer_resolution(True)
        src = self.source
        try:
            while not self.stop_event.is_set():
                t0 = time.perf_counter()
                s = self.settings
                if not self.has_clients() or self.is_paused():
                    src.reset()
                    self.stop_event.wait(0.05)
                    continue
                try:
                    frame = src.grab(s.monitor)
                except Exception:
                    src.close()
                    self.stop_event.wait(0.25)
                    continue
                if frame is None:                       # nothing changed
                    self.stop_event.wait(0.002)
                    continue
                with self.cond:
                    self.slot = frame
                    self.cond.notify()
                rest = 1.0 / max(5, s.fps) - (time.perf_counter() - t0)
                if rest > 0:
                    self.stop_event.wait(rest)
        finally:
            timer_resolution(False)
            src.close()

    def _encode_loop(self):
        while not self.stop_event.is_set():
            with self.cond:
                while self.slot is None and not self.stop_event.is_set():
                    self.cond.wait(0.2)
                frame, self.slot = self.slot, None
            if frame is None:
                continue
            t0 = time.perf_counter()
            self.frames += 1
            payloads = self._encode(frame[0], frame[1], self.settings, self.frames, self.wanted_widths())
            self.encode_ms = (time.perf_counter() - t0) * 1000
            self.publish(payloads)

    @staticmethod
    def _encode(size, raw, s, seq, widths):
        base = Image.frombuffer("RGB", size, raw, "raw", "BGRX", 0, 1)
        out = {}
        for max_w in widths:
            img = base
            if max_w and img.width > max_w:
                factor = img.width // max_w
                if factor >= 2:                  # integer box reduce is ~4x faster than a resize
                    img = img.reduce(factor)
                if img.width > max_w:
                    img = img.resize((max_w, max(2, int(img.height * max_w / img.width))), Image.BOX)
            buf = io.BytesIO()
            buf.write(struct.pack("<IHH", seq & 0xFFFFFFFF, img.width, img.height))
            # 4:2:0 chroma is much faster to encode; keep full chroma only for top quality
            img.save(buf, "JPEG", quality=s.quality, subsampling=0 if s.quality >= 93 else 2)
            out[max_w] = buf.getvalue()
        return out
