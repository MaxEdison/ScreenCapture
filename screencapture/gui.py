"""Desktop control window (tkinter, dark theme, English + Persian)."""

import threading
import tkinter as tk
from pathlib import Path
from tkinter import ttk

from . import system
from .i18n import LANGUAGES, make_translator
from .server import ScreenServer
from .settings import PRESETS, Settings

try:
    import qrcode
    from PIL import ImageTk
except ImportError:  # QR code is optional
    qrcode = None

FONT_DIR = Path(__file__).resolve().parent / "assets" / "fonts"

BG, CARD, CARD2 = "#0b0f1a", "#131a2b", "#1b2440"
TEXT, MUTED = "#e8ecf8", "#7b86a6"
ACCENT, OK, DANGER = "#6c5ce7", "#00d68f", "#ff5c7a"

RESOLUTIONS = [0, 2560, 1920, 1600, 1280, 960]


_RTL = False                       # set by App when the Persian UI is active


def _rtl(text):
    """Tk lays text out as a left-to-right paragraph; an RTL embedding makes mixed
    Persian + English lines (e.g. 'Wi-Fi') read in the right order."""
    return f"‫{text}‬" if _RTL and text else text


class RtlLabel(tk.Label):
    def __init__(self, master, **kw):
        if "text" in kw:
            kw["text"] = _rtl(kw["text"])
        super().__init__(master, **kw)

    def configure(self, cnf=None, **kw):
        if "text" in kw:
            kw["text"] = _rtl(kw["text"])
        return super().configure(cnf, **kw)

    config = configure


class Btn(RtlLabel):
    """Flat button with hover effect."""

    def __init__(self, master, text, command, font, bg=CARD2, fg=TEXT, hover=ACCENT, padx=16, pady=9):
        super().__init__(master, text=text, bg=bg, fg=fg, font=font, padx=padx, pady=pady, cursor="hand2")
        self._bg, self._hover, self._cmd = bg, hover, command
        self.bind("<Enter>", lambda e: self.config(bg=self._hover))
        self.bind("<Leave>", lambda e: self.config(bg=self._bg))
        self.bind("<Button-1>", lambda e: self._cmd())

    def recolor(self, bg, hover=None):
        self._bg = bg
        self._hover = hover or self._hover
        self.config(bg=bg)


class App:
    def __init__(self):
        self.settings = Settings.load()
        self.server = None
        self.stopping = False
        self.error = None            # (title, subtitle) while a start failed
        self.paused = False
        self.prev_stats = (0, 0)
        self.qr_image = None
        self.main_url = ""
        self.adv_open = False

        for name in ("Vazirmatn-Regular.ttf", "Vazirmatn-Bold.ttf"):    # before Tk() so Tk can see them
            system.load_private_font(FONT_DIR / name)

        self.root = root = tk.Tk()
        root.title("ScreenCapture")
        root.configure(bg=BG)
        scale = root.winfo_fpixels("1i") / 96
        sw, sh = root.winfo_screenwidth(), root.winfo_screenheight()
        w, h = min(int(960 * scale), sw - 40), min(int(690 * scale), sh - 90)
        root.geometry(f"{w}x{h}+{(sw - w) // 2}+{max(0, (sh - h) // 2 - 20)}")
        root.minsize(min(int(860 * scale), w), min(int(620 * scale), h))
        root.option_add("*TCombobox*Listbox.background", CARD2)
        root.option_add("*TCombobox*Listbox.foreground", TEXT)
        root.option_add("*TCombobox*Listbox.selectBackground", ACCENT)

        self.var_monitor = tk.StringVar()
        self.var_res = tk.StringVar()
        self.var_fps = tk.IntVar(value=self.settings.fps)
        self.var_quality = tk.IntVar(value=self.settings.quality)
        self.var_cursor = tk.BooleanVar(value=self.settings.show_cursor)
        self.var_autostart = tk.BooleanVar(value=self.settings.autostart)
        self.var_port = tk.StringVar(value=str(self.settings.port))
        self.var_pin = tk.StringVar(value=self.settings.pin)

        self.rebuild()
        root.protocol("WM_DELETE_WINDOW", self.close)
        root.after(1000, self._tick)
        if self.settings.autostart:
            root.after(600, self.start)

    # ------------------------------------------------------------------ language / fonts
    def _setup_language(self):
        self.lang = self.settings.language
        self.tr = make_translator(self.lang)
        self.rtl = self.lang == "fa"
        self.A = "e" if self.rtl else "w"                  # text anchor / grid sticky
        self.SIDE = "right" if self.rtl else "left"        # pack side for "first" element
        self.JUSTIFY = "right" if self.rtl else "left"
        self.family = "Vazirmatn" if self.rtl else "Segoe UI"
        global _RTL
        _RTL = self.rtl

    def font(self, size=10, bold=False):
        return (self.family, size, "bold" if bold else "normal")

    def _style(self):
        st = ttk.Style(self.root)
        st.theme_use("clam")
        st.configure("TCombobox", fieldbackground=CARD2, background=CARD2, foreground=TEXT, arrowcolor=TEXT,
                     bordercolor=CARD2, lightcolor=CARD2, darkcolor=CARD2, padding=6)
        st.configure("Horizontal.TScale", background=ACCENT, troughcolor=CARD2, bordercolor=CARD2,
                     lightcolor=ACCENT, darkcolor=ACCENT, sliderlength=22, troughrelief="flat")
        st.map("Horizontal.TScale", background=[("active", "#8c7ff0")])
        st.map("TCombobox", fieldbackground=[("readonly", CARD2)], foreground=[("readonly", TEXT)],
               selectbackground=[("readonly", CARD2)], selectforeground=[("readonly", TEXT)])

    def label(self, parent, text, size=10, color=TEXT, bold=False, **kw):
        kw.setdefault("justify", self.JUSTIFY)
        return RtlLabel(parent, text=text, bg=parent["bg"], fg=color, font=self.font(size, bold), **kw)

    def button(self, parent, text, command, **kw):
        kw.setdefault("font", self.font(10, True))
        return Btn(parent, text, command, **kw)

    # ------------------------------------------------------------------ build
    def rebuild(self):
        """(Re)create every widget. Called at startup and when the language changes."""
        for child in self.root.winfo_children():
            child.destroy()
        self._setup_language()
        self._style()
        self.monitors = system.list_monitors()
        root = self.root
        main_col, side_col = (1, 0) if self.rtl else (0, 1)
        root.columnconfigure(main_col, weight=5)
        root.columnconfigure(side_col, weight=4)
        root.rowconfigure(0, weight=1)

        # ---- main column: status + connect + live stats
        left = tk.Frame(root, bg=BG)
        left.grid(row=0, column=main_col, sticky="nsew", padx=(24, 12) if not self.rtl else (12, 24), pady=24)
        left.rowconfigure(2, weight=1)
        left.columnconfigure(0, weight=1)

        head = tk.Frame(left, bg=BG)
        head.grid(row=0, column=0, sticky="ew")
        head.columnconfigure(0, weight=1)
        titles = tk.Frame(head, bg=BG)
        titles.grid(row=0, column=0, sticky=self.A)
        self.label(titles, "ScreenCapture" if not self.rtl else "اسکرین‌کپچر",
                   22, TEXT, True).pack(anchor=self.A)
        self.label(titles, self.tr("tagline"), 10, MUTED).pack(anchor=self.A)
        other = "fa" if self.lang == "en" else "en"
        self.button(head, LANGUAGES[other], self.switch_language, padx=12, pady=6, bg=CARD,
                    hover=CARD2).grid(row=0, column=1, sticky="ne")

        ctrl = tk.Frame(left, bg=CARD, padx=20, pady=18)
        ctrl.grid(row=1, column=0, sticky="ew", pady=(18, 14))
        ctrl.columnconfigure(1, weight=1)
        dot_col, txt_col, btn_col = (3, 2, 0) if self.rtl else (0, 1, 2)
        ctrl.columnconfigure(txt_col, weight=1)
        ctrl.columnconfigure(1 if not self.rtl else 2, weight=1)
        self.dot = tk.Label(ctrl, text="●", bg=CARD, fg=MUTED, font=("Segoe UI", 20))
        self.dot.grid(row=0, column=dot_col, rowspan=2, padx=(0, 12) if not self.rtl else (12, 0))
        self.status = self.label(ctrl, "", 14, TEXT, True)
        self.status.grid(row=0, column=txt_col, sticky=self.A)
        self.status_sub = self.label(ctrl, "", 9, MUTED, wraplength=300)
        self.status_sub.grid(row=1, column=txt_col, sticky=self.A)
        btns = tk.Frame(ctrl, bg=CARD)
        btns.grid(row=0, column=btn_col, rowspan=2, padx=(14, 0) if not self.rtl else (0, 14))
        self.start_btn = self.button(btns, "", self.toggle, bg=OK, fg="#04210f", hover="#2cf0aa",
                                     font=self.font(11, True), padx=20, pady=10)
        self.start_btn.pack(side=self.SIDE)
        self.pause_btn = self.button(btns, "", self.toggle_pause, padx=14, pady=10)

        self.body = tk.Frame(left, bg=CARD, padx=20, pady=18)
        self.body.grid(row=2, column=0, sticky="nsew")
        self.body.columnconfigure(0, weight=1)
        self._build_howto()
        self._build_connect()

        stats = tk.Frame(left, bg=BG)
        stats.grid(row=3, column=0, sticky="ew", pady=(14, 0))
        self.stat_labels = {}
        keys = (("viewers", "st_viewers"), ("fps", "st_fps"), ("mbps", "st_mbps"), ("enc", "st_enc"))
        for i, (key, title) in enumerate(keys):
            cell = tk.Frame(stats, bg=CARD, padx=14, pady=10)
            cell.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 8, 0))
            stats.columnconfigure(i, weight=1)
            self.stat_labels[key] = self.label(cell, "0", 16, TEXT, True)
            self.stat_labels[key].pack(anchor=self.A)
            self.label(cell, self.tr(title), 8, MUTED).pack(anchor=self.A)

        # ---- side column: settings
        right = tk.Frame(root, bg=CARD, padx=22, pady=20)
        right.grid(row=0, column=side_col, sticky="nsew", padx=(12, 24) if not self.rtl else (24, 12), pady=24)
        right.columnconfigure(0, weight=1)
        self._build_settings(right)

        self._sync_widgets()
        self._bind_live()
        self._refresh_status()

    def _build_settings(self, right):
        A, tr = self.A, self.tr
        self.label(right, tr("settings"), 15, TEXT, True).grid(row=0, column=0, sticky=A)
        self.label(right, tr("settings_hint"), 9, MUTED).grid(row=1, column=0, sticky=A)

        self.label(right, tr("quality_mode"), 10, TEXT, True).grid(row=2, column=0, sticky=A, pady=(16, 6))
        seg = tk.Frame(right, bg=CARD)
        seg.grid(row=3, column=0, sticky="ew")
        self.preset_btns = {}
        for i, key in enumerate(PRESETS):
            b = self.button(seg, tr(key), lambda k=key: self.pick_preset(k), padx=10, pady=8)
            b.grid(row=0, column=i, sticky="ew", padx=(0 if i == 0 else 6, 0))
            seg.columnconfigure(i, weight=1)
            self.preset_btns[key] = b
        self.preset_hint = self.label(right, "", 9, MUTED)
        self.preset_hint.grid(row=4, column=0, sticky=A, pady=(6, 0))

        self.label(right, tr("screen_to_share"), 10, TEXT, True).grid(row=5, column=0, sticky=A, pady=(16, 6))
        names = [tr("all_screens") if i == 0 else tr("screen_n", n=i, w=w, h=h) for i, w, h in self.monitors]
        self.cb_monitor = ttk.Combobox(right, textvariable=self.var_monitor, state="readonly", values=names)
        self.cb_monitor.grid(row=6, column=0, sticky="ew")

        def check(text, var, row, pad):
            tk.Checkbutton(right, text=_rtl(text), variable=var, bg=CARD, fg=TEXT, selectcolor=CARD2,
                           activebackground=CARD, activeforeground=TEXT, bd=0, highlightthickness=0,
                           font=self.font(10), justify=self.JUSTIFY).grid(row=row, column=0, sticky=A, pady=pad)

        check(tr("show_cursor"), self.var_cursor, 7, (14, 0))
        check(tr("autostart"), self.var_autostart, 8, (4, 0))

        self.adv_toggle = self.button(right, "", self.toggle_adv, bg=CARD, hover=CARD2, fg=MUTED, padx=0, pady=6)
        self.adv_toggle.grid(row=9, column=0, sticky=A, pady=(14, 0))
        self.adv = tk.Frame(right, bg=CARD)
        self.adv.columnconfigure(0, weight=1)

        self.label(self.adv, tr("framerate"), 10, TEXT, True).grid(row=0, column=0, sticky=A, pady=(6, 0))
        self.sl_fps = self._slider(self.adv, self.var_fps, 15, 120, " fps")
        self.sl_fps.grid(row=1, column=0, sticky="ew")
        self.label(self.adv, tr("jpeg_quality"), 10, TEXT, True).grid(row=2, column=0, sticky=A, pady=(8, 0))
        self.sl_q = self._slider(self.adv, self.var_quality, 30, 95, "%")
        self.sl_q.grid(row=3, column=0, sticky="ew")
        self.label(self.adv, tr("max_res"), 10, TEXT, True).grid(row=4, column=0, sticky=A, pady=(8, 4))
        self.cb_res = ttk.Combobox(self.adv, textvariable=self.var_res, state="readonly",
                                   values=[self._res_name(r) for r in RESOLUTIONS])
        self.cb_res.grid(row=5, column=0, sticky="ew")

        row = tk.Frame(self.adv, bg=CARD)
        row.grid(row=6, column=0, sticky="ew", pady=(12, 0))
        row.columnconfigure((0, 1), weight=1)
        for col, (title, var) in enumerate(((tr("port"), self.var_port), (tr("pin_opt"), self.var_pin))):
            c = (1 - col) if self.rtl else col
            self.label(row, title, 10, TEXT, True).grid(row=0, column=c, sticky=A, padx=(0 if c == 0 else 10, 0))
            tk.Entry(row, textvariable=var, bg=CARD2, fg=TEXT, insertbackground=TEXT, relief="flat",
                     font=self.font(11), width=10, justify="left").grid(
                row=1, column=c, sticky="ew", padx=(0 if c == 0 else 10, 0), ipady=6)
        self.label(self.adv, tr("restart_note"), 8, MUTED, wraplength=330).grid(row=7, column=0, sticky=A, pady=(6, 0))
        if self.adv_open:
            self.adv.grid(row=10, column=0, sticky="ew")
        self.adv_toggle.config(text=self._adv_text())

    def _slider(self, parent, var, lo, hi, suffix=""):
        row = tk.Frame(parent, bg=CARD)
        val = self.label(row, "", 10, MUTED)
        scale = ttk.Scale(row, from_=lo, to=hi, orient="horizontal", variable=var,
                          command=lambda v: val.config(text=f"{int(float(v))}{suffix}"))
        scale.pack(side=self.SIDE, fill="x", expand=True, pady=6)
        val.pack(side=self.SIDE, padx=10)
        row._val, row._suffix = val, suffix
        return row

    def _build_howto(self):
        tr = self.tr
        self.howto = tk.Frame(self.body, bg=CARD)
        self.label(self.howto, tr("getting_started"), 13, TEXT, True).pack(anchor=self.A)
        for num, key in (("1", "step1"), ("2", "step2"), ("3", "step3")):
            r = tk.Frame(self.howto, bg=CARD)
            r.pack(fill="x", pady=(14, 0))
            tk.Label(r, text=num, bg=ACCENT, fg="white", font=("Segoe UI", 11, "bold"), width=3, pady=4).pack(
                side=self.SIDE, anchor="n")
            t = tk.Frame(r, bg=CARD)
            t.pack(side=self.SIDE, padx=12)
            self.label(t, tr(key), 10, TEXT, True).pack(anchor=self.A)
            self.label(t, tr(key + "_sub"), 9, MUTED, wraplength=340).pack(anchor=self.A)

    def _build_connect(self):
        tr = self.tr
        self.connect = tk.Frame(self.body, bg=CARD)
        self.label(self.connect, tr("open_phone"), 13, TEXT, True).pack(anchor=self.A)
        self.label(self.connect, tr("open_phone_sub"), 9, MUTED).pack(anchor=self.A)
        mid = tk.Frame(self.connect, bg=CARD)
        mid.pack(fill="x", pady=(14, 0))
        self.qr_label = tk.Label(mid, bg=CARD)
        self.qr_label.pack(side=self.SIDE, anchor="n")
        info = tk.Frame(mid, bg=CARD)
        info.pack(side=self.SIDE, padx=18, anchor="n")
        self.url_label = self.label(info, "", 14, OK, True)
        self.url_label.pack(anchor=self.A)
        self.url_extra = self.label(info, "", 9, MUTED)
        self.url_extra.pack(anchor=self.A, pady=(4, 8))
        self.copy_btn = self.button(info, tr("copy"), self.copy_url, padx=12, pady=7)
        self.copy_btn.pack(anchor=self.A)
        self.button(info, tr("firewall"), self.fix_firewall, bg=CARD, hover=CARD2, fg=MUTED,
                    font=self.font(9), padx=0, pady=8).pack(anchor=self.A, pady=(6, 0))
        self.devices_label = self.label(self.connect, "", 9, MUTED)
        self.devices_label.pack(anchor=self.A, pady=(12, 0))

    # ------------------------------------------------------------------ settings <-> widgets
    def _res_name(self, r):
        return {0: self.tr("native"), 1920: self.tr("res_1920"), 1280: self.tr("res_1280")}.get(
            r, self.tr("res_px", n=r))

    def _adv_text(self):
        return f"{self.tr('advanced')}  {chr(0x25b4) if self.adv_open else chr(0x25be)}"

    def _sync_widgets(self):
        s = self.settings
        idx = next((i for i, m in enumerate(self.monitors) if m[0] == s.monitor), 0)
        self.cb_monitor.current(idx)
        self.cb_res.current(RESOLUTIONS.index(s.max_width) if s.max_width in RESOLUTIONS else 2)
        self.var_fps.set(s.fps)
        self.var_quality.set(s.quality)
        for sl, v in ((self.sl_fps, s.fps), (self.sl_q, s.quality)):
            sl._val.config(text=f"{v}{sl._suffix}")
        self._refresh_presets()

    def _refresh_presets(self):
        s = self.settings
        for key, b in self.preset_btns.items():
            b.recolor(ACCENT if key == s.preset else CARD2, ACCENT)
        self.preset_hint.config(text=self.tr(s.preset + "_hint") if s.preset in PRESETS else self.tr("custom_hint"))

    def _bind_live(self):
        for w in (self.cb_monitor, self.cb_res):
            w.bind("<<ComboboxSelected>>", lambda e: self.apply(custom=True))
        for v in (self.var_fps, self.var_quality):
            v.trace_add("write", lambda *a: self.apply(custom=True))
        self.var_cursor.trace_add("write", lambda *a: self.apply())
        self.var_autostart.trace_add("write", lambda *a: self.apply())

    def apply(self, custom=False):
        """Copy widget values into the shared Settings object (the server reads it live)."""
        s = self.settings
        try:
            s.monitor = self.monitors[self.cb_monitor.current()][0]
        except IndexError:
            pass
        s.show_cursor = self.var_cursor.get()
        s.autostart = self.var_autostart.get()
        if custom:
            s.fps, s.quality = int(self.var_fps.get()), int(self.var_quality.get())
            ri = self.cb_res.current()
            s.max_width = RESOLUTIONS[ri] if ri >= 0 else s.max_width
            if (s.fps, s.quality, s.max_width) != tuple(PRESETS.get(s.preset, {}).values()):
                s.preset = "custom"
        s.clamp()
        s.save()
        self._refresh_presets()

    def pick_preset(self, name):
        self.settings.apply_preset(name)
        self.settings.save()
        self._sync_widgets()

    def toggle_adv(self):
        self.adv_open = not self.adv_open
        if self.adv_open:
            self.adv.grid(row=10, column=0, sticky="ew")
        else:
            self.adv.grid_forget()
        self.adv_toggle.config(text=self._adv_text())

    def switch_language(self):
        self.settings.language = "fa" if self.settings.language == "en" else "en"
        self.settings.save()
        self.rebuild()
        if self.server:
            self._show_connect()

    # ------------------------------------------------------------------ status / actions
    def _refresh_status(self):
        tr = self.tr
        running = self.server is not None
        if self.stopping:
            title, sub, color = tr("stopping"), "", MUTED
        elif self.error:
            (title, sub), color = self.error, DANGER
        elif running and self.paused:
            title, sub, color = tr("paused"), tr("paused_sub"), "#ffb347"
        elif running:
            n = self.server.stats()["clients"]
            title, color = tr("sharing_on"), OK
            sub = tr("viewers_n", n=n) if n else tr("waiting")
        else:
            title, sub, color = tr("stopped"), tr("press_start"), MUTED
        self.dot.config(fg=color)
        self.status.config(text=title)
        self.status_sub.config(text=sub)

        if running:
            self.start_btn.config(text=tr("stop"), fg="white")
            self.start_btn.recolor(DANGER, "#ff8099")
            self.pause_btn.config(text=tr("resume") if self.paused else tr("pause"))
            if not self.pause_btn.winfo_manager():
                self.pause_btn.pack(side=self.SIDE, padx=(8, 0) if not self.rtl else (0, 8))
            self._show_body(True)
        else:
            self.start_btn.config(text=tr("start"), fg="#04210f")
            self.start_btn.recolor(MUTED if self.stopping else OK, "#2cf0aa")
            self.pause_btn.pack_forget()
            self._show_body(False)

    def _show_body(self, running):
        self.howto.pack_forget()
        self.connect.pack_forget()
        (self.connect if running else self.howto).pack(fill="both", expand=True)

    def toggle(self):
        if self.stopping:
            return
        self.stop() if self.server else self.start()

    def start(self):
        if self.server or self.stopping:
            return
        s = self.settings
        try:
            s.port = int(self.var_port.get())
        except ValueError:
            s.port = 8000
        s.pin = self.var_pin.get()
        s.clamp()
        self.var_port.set(str(s.port))
        s.save()
        server = ScreenServer(s)
        self.error = None
        try:
            server.start()
        except OSError:
            self.error = (self.tr("port_busy"), self.tr("port_busy_sub", port=s.port))
            self._refresh_status()
            return
        except Exception as exc:
            self.error = (self.tr("start_failed"), str(exc)[:80])
            self._refresh_status()
            return
        self.server = server
        self.paused = False
        self.prev_stats = (0, 0)
        self._show_connect()
        self._refresh_status()

    def stop(self):
        """Update the UI at once; the server shuts down in the background."""
        server, self.server = self.server, None
        self.stopping, self.paused = True, False
        for lbl in self.stat_labels.values():
            lbl.config(text="0")
        self._refresh_status()

        def work():
            try:
                server.stop()
            finally:
                self.stopping = False

        threading.Thread(target=work, daemon=True).start()
        self.root.after(100, self._wait_stopped)

    def _wait_stopped(self):
        if self.stopping:
            self.root.after(100, self._wait_stopped)
        else:
            self._refresh_status()

    def toggle_pause(self):
        if self.server:
            self.paused = not self.paused
            self.server.set_paused(self.paused)
            self._refresh_status()

    def _show_connect(self):
        s = self.settings
        urls = [f"http://{ip}:{s.port}" for ip in (system.get_lan_ips() or ["localhost"])]
        self.main_url = urls[0]
        self.url_label.config(text=urls[0].replace("http://", ""))
        lines = [self.tr("pin_line", pin=s.pin)] if s.pin else []
        if len(urls) > 1:
            lines += [self.tr("other_addr")] + [u.replace("http://", "") for u in urls[1:4]]
        self.url_extra.config(text="\n".join(lines))
        self.qr_image = None
        self.qr_label.config(image="")
        if qrcode:
            try:
                qr = qrcode.QRCode(border=2, box_size=6)
                qr.add_data(urls[0] + (f"/?pin={s.pin}" if s.pin else ""))
                self.qr_image = ImageTk.PhotoImage(
                    qr.make_image(fill_color="#0b0f1a", back_color="white").get_image())
                self.qr_label.config(image=self.qr_image)
            except Exception:
                pass

    def copy_url(self):
        self.root.clipboard_clear()
        self.root.clipboard_append(self.main_url)
        self.copy_btn.config(text=self.tr("copied"))
        self.root.after(1500, lambda: self.copy_btn.winfo_exists() and self.copy_btn.config(text=self.tr("copy")))

    def fix_firewall(self):
        system.open_firewall(self.settings.port)

    # ------------------------------------------------------------------ live stats
    def _tick(self):
        if self.server:
            st = self.server.stats()
            frames, nbytes = st["frames"], st["bytes"]
            dframes, dbytes = frames - self.prev_stats[0], nbytes - self.prev_stats[1]
            self.prev_stats = (frames, nbytes)
            self.stat_labels["viewers"].config(text=str(st["clients"]))
            self.stat_labels["fps"].config(text=str(dframes // max(1, st["clients"])))
            self.stat_labels["mbps"].config(text=f"{dbytes * 8 / 1e6:.1f}")
            self.stat_labels["enc"].config(text=f"{st['encode_ms']:.0f}")
            self.devices_label.config(
                text=f"{self.tr('devices')}  {',  '.join(st['devices'])}" if st["devices"] else "")
            if not self.error and not self.stopping and not self.paused:
                self._refresh_status()
        self.root.after(1000, self._tick)

    def close(self):
        if self.server:
            threading.Thread(target=self.server.stop, daemon=True).start()
        self.settings.save()
        self.root.destroy()

    def run(self):
        self.root.mainloop()
