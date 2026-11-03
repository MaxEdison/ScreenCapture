"""User settings, persisted to settings.json next to main.py."""

import json
from dataclasses import asdict, dataclass, fields
from pathlib import Path

APP_DIR = Path(__file__).resolve().parent.parent
SETTINGS_FILE = APP_DIR / "settings.json"

PRESETS = {
    "fastest":  {"fps": 60, "quality": 60, "max_width": 960},
    "balanced": {"fps": 60, "quality": 75, "max_width": 1920},
    "sharpest": {"fps": 60, "quality": 88, "max_width": 0},
}


@dataclass
class Settings:
    language: str = "en"        # "en" or "fa"
    port: int = 8000
    monitor: int = 1            # index in mss.monitors (0 = all screens)
    preset: str = "balanced"    # fastest / balanced / sharpest / custom
    fps: int = 60
    quality: int = 75           # JPEG quality 30-95
    max_width: int = 1920       # 0 = native resolution
    show_cursor: bool = True
    autostart: bool = False     # start sharing as soon as the app opens
    pin: str = ""

    def clamp(self):
        self.language = self.language if self.language in ("en", "fa") else "en"
        self.port = max(1024, min(65535, int(self.port)))
        self.fps = max(5, min(144, int(self.fps)))
        self.quality = max(30, min(95, int(self.quality)))
        self.max_width = max(0, int(self.max_width))
        self.monitor = max(0, int(self.monitor))
        self.pin = str(self.pin).strip()[:12]
        return self

    def apply_preset(self, name):
        if name in PRESETS:
            self.preset = name
            for key, value in PRESETS[name].items():
                setattr(self, key, value)

    @classmethod
    def load(cls):
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            known = {f.name for f in fields(cls)}
            return cls(**{k: v for k, v in data.items() if k in known}).clamp()
        except (OSError, ValueError, TypeError):
            return cls()

    def save(self):
        try:
            SETTINGS_FILE.write_text(json.dumps(asdict(self), indent=2), encoding="utf-8")
        except OSError:
            pass
