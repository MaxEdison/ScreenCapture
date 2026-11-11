"""OS / network helpers (DPI, cursor, monitors, LAN addresses, firewall, fonts)."""

import ctypes
import os
import socket

import mss

MSS = getattr(mss, "MSS", None) or mss.mss     # mss.mss was renamed to mss.MSS

FR_PRIVATE = 0x10


def enable_dpi_awareness():
    """Make screen coordinates real pixels (needed for crisp capture and a correct cursor)."""
    if os.name != "nt":
        return
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(2)
    except Exception:
        try:
            ctypes.windll.user32.SetProcessDPIAware()
        except Exception:
            pass


def timer_resolution(on):
    """1 ms Windows timer, so frame pacing is accurate (default is ~15 ms)."""
    if os.name == "nt":
        try:
            (ctypes.windll.winmm.timeBeginPeriod if on else ctypes.windll.winmm.timeEndPeriod)(1)
        except Exception:
            pass


class _POINT(ctypes.Structure):
    _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]


def get_cursor_pos():
    if os.name != "nt":
        return None
    pt = _POINT()
    if ctypes.windll.user32.GetCursorPos(ctypes.byref(pt)):
        return pt.x, pt.y
    return None


def list_monitors():
    """[(index, width, height)]; index 0 = all screens combined (only if more than one)."""
    try:
        with MSS() as sct:
            mons = sct.monitors
        out = [(0, mons[0]["width"], mons[0]["height"])] if len(mons) > 2 else []
        out += [(i, m["width"], m["height"]) for i, m in enumerate(mons[1:], 1)]
        return out
    except Exception:
        return [(1, 0, 0)]


def get_lan_ips():
    """LAN IPv4 addresses of this computer, most likely one first."""
    found = []

    def add(ip):
        if ip and not ip.startswith(("127.", "169.254.", "0.")) and ip not in found:
            found.append(ip)

    for target in ("10.255.255.255", "192.168.255.255", "8.8.8.8"):
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
                s.connect((target, 1))
                add(s.getsockname()[0])
        except OSError:
            pass
    try:
        for ip in socket.gethostbyname_ex(socket.gethostname())[2]:
            add(ip)
    except OSError:
        pass

    def private_rank(ip):
        a, b = (int(x) for x in ip.split(".")[:2])
        return 0 if ip.startswith("192.168.") else 1 if a == 10 else 2 if (a == 172 and 16 <= b <= 31) else 3

    return sorted(found, key=private_rank)


def open_firewall(port):
    """Ask Windows (UAC prompt) to allow incoming connections on `port` for private networks."""
    if os.name != "nt":
        return False
    args = (f'advfirewall firewall add rule name="ScreenCapture {port}" dir=in '
            f'action=allow protocol=TCP localport={port} profile=private')
    return ctypes.windll.shell32.ShellExecuteW(None, "runas", "netsh", args, None, 0) > 32


def load_private_font(path):
    """Make a .ttf usable by this process only (nothing is installed system-wide)."""
    if os.name != "nt":
        return False
    try:
        return ctypes.windll.gdi32.AddFontResourceExW(str(path), FR_PRIVATE, 0) > 0
    except Exception:
        return False
