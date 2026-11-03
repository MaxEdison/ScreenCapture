"""ScreenCapture: offline, low-latency screen sharing over your local Wi-Fi / modem.

Run:  python main.py
"""

from screencapture.system import enable_dpi_awareness

enable_dpi_awareness()          # must happen before any window is created

from screencapture.gui import App  # noqa: E402

if __name__ == "__main__":
    App().run()
