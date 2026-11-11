# ScreenCapture 🖥️ ➜ 📱

**Share your computer screen to any phone, tablet or laptop on the same Wi-Fi / modem.
Offline, low-latency, zero setup on the viewing device. Just open a link in Chrome.**

[فارسی](#فارسی) · [Quick start](#-quick-start) · [How it works](#-how-it-works) · [Troubleshooting](#-troubleshooting)

---

## ✨ Features

| | |
| --- | --- |
| ⚡ **Low latency** | WebSocket + `TCP_NODELAY`; a viewer always receives the *newest* frame, never a backlog. |
| 🎮 **GPU capture** | DXGI desktop duplication on Windows (~3x faster than GDI), automatic fallback to standard capture. |
| 📱 **Fast on phones** | Every viewer gets its own frame size. The viewer page measures decode time and ping and steps between 960 / 1280 / 1600 / 1920 px automatically. |
| 🖱️ **Instant pointer** | The mouse cursor is sent separately and drawn by the viewer, so it never waits for video. |
| 🌍 **English + Persian** | App and viewer in both languages (RTL, [Vazirmatn](https://github.com/rastikerdar/vazirmatn) font bundled). |
| 🟢 **Beginner friendly** | One Start button, a QR code, three quality modes. Advanced options are tucked away. |
| 🔒 **Optional PIN** | Protect the stream; the QR code already contains the PIN. |
| 👥 **Multi-viewer** | Each frame is encoded once per size and shared by everyone. |
| 📴 **100 % offline** | No internet, cloud or CDN needed after installing. Fonts and the viewer page are bundled. |

Extras: pause button, connected-devices list, screenshot button on the viewer, auto-start option, MJPEG fallback (`/stream`).

## 🚀 Quick start

**Windows**

1. Install [Python 3.10+](https://www.python.org/downloads/) (tick *Add Python to PATH*).
2. Double-click **`windows-install.bat`** (internet needed once).
3. Double-click **`windows-run.bat`**.
4. Press **Start sharing**, then scan the QR code with your phone (same Wi-Fi / modem), or type the address into Chrome.

Manual:

```bash
pip install -r requirements.txt
python main.py
```

Linux and macOS use the standard capture mode (the pointer overlay is Windows-only).

## 🔧 How it works

```
 Screen ─► grab thread ─► newest frame only ─► encode thread ─► JPEG (once per size)
                                                                   │
              viewer page ◄── WebSocket (ACK per frame, max 2 in flight) ◄┘
              decodes + paints immediately; cursor arrives on its own channel
```

- A slow viewer never builds a queue: when it is ready it gets the latest frame, older ones are dropped.
- Unchanged screens are not re-encoded or re-sent.
- The viewer adapts its frame size to its own decode speed and network ping (Quality: **Auto**), or you can pin a size.

### Quality modes

| Mode | Resolution | JPEG quality | Best for |
| --- | --- | --- | --- |
| Fastest | 960 px | 60 | weak Wi-Fi, lowest delay |
| Balanced | up to 1920 px | 75 | everyday use (default) |
| Sharpest | native | 88 | text, design work |

## 📁 Project layout

```
main.py                  entry point
requirements.txt         all dependencies (GPU capture is optional)
windows-install.bat      installs dependencies
windows-run.bat          starts the app without a console window
screencapture/
  gui.py                 desktop window (tkinter)
  i18n.py                English / Persian strings
  server.py              WebSocket + MJPEG server, per-viewer sizes
  capture.py             screen grabbing and JPEG encoding
  settings.py            settings + presets (saved to settings.json)
  system.py              Windows / network helpers
  web/                   viewer page + WOFF2 fonts (served offline)
  assets/fonts/          TTF fonts for the app + OFL licence
```

## 🩺 Troubleshooting

| Problem | Fix |
| --- | --- |
| Phone cannot open the address | Same Wi-Fi? Click **Can't connect? Fix firewall** in the app (one admin prompt). Set the Windows network to *Private*. |
| Works on the laptop but not the phone | The router may block device-to-device traffic (guest Wi-Fi / "AP isolation"). Use the main Wi-Fi or a phone hotspot. |
| "Port is busy" | Open **Advanced** and change the port. |
| Choppy on the phone | Keep viewer Quality on **Auto**, use **Fastest** mode, prefer 5 GHz Wi-Fi. |
| Black screen for protected video / UAC | Windows does not allow capturing those. |

Endpoints: `/` viewer · `/ws` WebSocket stream · `/stream` MJPEG. With a PIN, append `?pin=1234`.

## 🤝 Contributing

Issues and pull requests are welcome.

## 📄 License

[GPL-3.0](LICENSE). The Vazirmatn font is under the SIL Open Font License (`screencapture/assets/fonts/OFL.txt`).

Based on [MaxEdison/ScreenCapture](https://github.com/MaxEdison/ScreenCapture) by Max Edison and AmirHossein Heidari, inspired by [ScreenTask](https://github.com/EslaMx7/ScreenTask).

---

<div dir="rtl">

## فارسی

**صفحه‌ی کامپیوترتان را روی گوشی، تبلت یا لپ‌تاپ دیگر که به همان Wi-Fi یا مودم وصل است نمایش دهید. آفلاین، با تأخیر خیلی کم و بدون نصب چیزی روی دستگاه مقصد؛ فقط یک لینک در Chrome.**

### شروع سریع (ویندوز)

1. [پایتون ۳٫۱۰ یا بالاتر](https://www.python.org/downloads/) را نصب کنید (گزینه‌ی *Add Python to PATH* را بزنید).
2. فایل **`windows-install.bat`** را اجرا کنید (فقط یک‌بار به اینترنت نیاز دارد).
3. فایل **`windows-run.bat`** را اجرا کنید.
4. دکمه‌ی **شروع اشتراک** را بزنید و با گوشی QR را اسکن کنید یا آدرس را در Chrome بزنید.

### ویژگی‌ها

- تأخیر خیلی کم با WebSocket و کپچر با کارت گرافیک.
- گوشی به‌طور خودکار اندازه‌ی تصویر را با سرعت خودش تنظیم می‌کند تا روان بماند.
- برنامه و صفحه‌ی گوشی فارسی و انگلیسی‌اند (فونت وزیرمتن داخل پروژه است).
- بدون نیاز به اینترنت بعد از نصب، رمز اختیاری، چند بیننده هم‌زمان، دکمه‌ی مکث و عکس‌گرفتن از صفحه.

### اگر گوشی وصل نشد

- هر دو دستگاه به یک مودم وصل باشند (نه Wi-Fi مهمان).
- در برنامه روی «وصل نمی‌شود؟ فایروال را رفع کن» بزنید.
- اگر روی لپ‌تاپ باز می‌شود ولی روی گوشی نه، روتر ارتباط بین دستگاه‌ها را بسته است؛ از هات‌اسپات گوشی استفاده کنید.

</div>
