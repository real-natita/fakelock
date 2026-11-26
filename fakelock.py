#!/usr/bin/env python3
"""CatCrypt-пранк: полноэкранный «локер» в стиле видео.

Что внутри:
  * заставка с логотипом (ассет вырезан из видео) и консольными строками
  * чёрный экран, маджентовый бокс, часы, ID компьютера, поле кода
  * всплывашка «замечена попытка снять блокировку»
  * звуки: alarm/beep/music вырезаны из видео (assets/sfx), клики синтез
  * Ctrl+M — выключить/включить звук, --no-music — запуск без музыки

Чего внутри НЕТ:
  * шифрования (никакого), доступа к файлам, сети, телеграма, автозапуска
  * требований денег, кошельков, таймеров до удаления

Любой код «разблокирует». Esc / Ctrl+Q — выход всегда.

Запуск:   python3 fakelock.py            (на весь экран)
          python3 fakelock.py --windowed (окно 1100x620, для проверки)
"""

import json
import os
import signal
import subprocess
import sys
import tempfile
import time
import tkinter as tk
from tkinter import font as tkfont

try:
    import numpy as np
except ImportError:
    np = None

try:
    from PIL import Image, ImageTk
except ImportError:
    Image = ImageTk = None

IS_WIN = sys.platform == "win32"

if getattr(sys, "frozen", False):          # запуск из собранного .exe
    BASE = getattr(sys, "_MEIPASS", os.path.dirname(sys.executable))
else:
    BASE = os.path.dirname(os.path.abspath(__file__))
ASSETS = os.path.join(BASE, "assets")
CAT_PNG = os.path.join(ASSETS, "cat.png")
PINK_PNG = os.path.join(ASSETS, "pink_art.png")
SFX_DIR = os.path.join(tempfile.gettempdir(), "catlock_sfx")
SR = 44100

BLACK = "#000000"
MAG = "#e000e0"          # основной маджентовый
MAG_BRIGHT = "#ff00ff"   # заливка поля ввода
MAG_DIM = "#8a1a8a"
MAG_FAINT = "#4a0a4a"
MAG_BAR = "#c800c8"


# ---------------------------------------------------------------- звук
def _env(n, a=0.005, r=0.03):
    t = np.arange(n) / SR
    dur = n / SR
    up = np.clip(t / max(a, 1e-5), 0, 1)
    dn = np.clip((dur - t) / max(r, 1e-5), 0, 1)
    return up * dn


def _tone(f, dur, vol=0.3, kind="sine", decay=3.0):
    n = int(SR * dur)
    ph = 2 * np.pi * f * np.arange(n) / SR
    w = np.sin(ph) if kind == "sine" else np.sign(np.sin(ph))
    return w * np.exp(-decay * np.arange(n) / n) * _env(n) * vol


def _sweep(f0, f1, dur, vol=0.3, kind="saw"):
    n = int(SR * dur)
    f = np.linspace(f0, f1, n)
    ph = 2 * np.pi * np.cumsum(f) / SR
    w = np.sin(ph) if kind == "sine" else (2 / np.pi) * np.arcsin(np.sin(ph))
    return w * _env(n, 0.01, 0.2) * vol


def _noise(dur, vol=0.3):
    n = int(SR * dur)
    return np.random.uniform(-1, 1, n) * _env(n, 0.001, dur) * vol


def _save(name, data):
    import wave

    os.makedirs(SFX_DIR, exist_ok=True)
    data = np.clip(data, -1, 1)
    pcm = (data * 32767).astype("<i2")
    with wave.open(os.path.join(SFX_DIR, name), "wb") as f:
        f.setnchannels(1)
        f.setsampwidth(2)
        f.setframerate(SR)
        f.writeframes(pcm.tobytes())


def build_sfx():
    if np is None:
        return
    if os.path.isfile(os.path.join(SFX_DIR, "boom.wav")):
        return
    _save("tick.wav", _tone(1750, 0.035, 0.10, "square", 30))
    _save("click.wav", np.concatenate([
        _noise(0.028, 0.28),
        _tone(900, 0.02, 0.06, "square", 30),
    ]))
    _save("boom.wav", np.concatenate([
        _sweep(120, 38, 0.7, 0.45, "saw"),
        _noise(0.18, 0.12),
    ]))
    z = _tone(96, 0.7, 0.32, "square", 1.0)
    z *= 1 + 0.55 * np.sin(2 * np.pi * 8 * np.arange(len(z)) / SR)
    _save("buzz.wav", z)
    _save("chime.wav", np.concatenate([
        _tone(720, 0.22, 0.20, "sine", 4),
        _tone(1080, 0.5, 0.16, "sine", 3),
    ]))
    _save("type.wav", _noise(0.015, 0.12))


class Sfx:
    """Звуки из видео лежат в assets/sfx (alarm, beep, music),
    синтезированные — в /tmp/opencode/catlock_sfx."""

    def __init__(self):
        self.on = True
        self.music_proc = None
        try:
            build_sfx()
        except Exception:
            pass

    def path(self, name):
        for d in (os.path.join(ASSETS, "sfx"), SFX_DIR):
            p = os.path.join(d, name + ".wav")
            if os.path.isfile(p):
                return p
        return None

    def _win_play(self, path, loop=False):
        import winsound
        flags = winsound.SND_FILENAME | winsound.SND_ASYNC
        if loop:
            flags |= winsound.SND_LOOP
        winsound.PlaySound(path, flags)

    def play(self, name, vol=1.0):
        if not self.on:
            return
        p = self.path(name)
        if not p:
            return
        try:
            if IS_WIN:
                self._win_play(p)
            else:
                subprocess.Popen(
                    ["paplay", f"--volume={int(65536 * min(vol, 1.0))}", p],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                    start_new_session=True)
        except Exception:
            pass

    def has(self, name):
        return self.path(name) is not None

    def start_music(self, vol=0.22):
        p = self.path("full") or self.path("music")
        if not p or not self.on:
            return None
        if IS_WIN:
            try:
                self._win_play(p, loop=True)
                self.music_proc = "win"
            except Exception:
                self.music_proc = None
            return self.music_proc
        try:
            self.music_proc = subprocess.Popen(
                ["paplay", f"--volume={int(65536 * vol)}", p],
                stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                start_new_session=True)
        except Exception:
            self.music_proc = None
        return self.music_proc

    def stop_music(self):
        if IS_WIN:
            try:
                import winsound
                winsound.PlaySound(None, winsound.SND_PURGE)
            except Exception:
                pass
            self.music_proc = None
            return
        if self.music_proc and self.music_proc.poll() is None:
            try:
                self.music_proc.terminate()
            except Exception:
                pass
        self.music_proc = None


# ---------------------------------------------------------------- утилиты
def pick_font(*names):
    have = set(tkfont.families())
    for n in names:
        if n in have:
            return n
    return names[-1]


def monitor_size():
    try:
        out = subprocess.run(["hyprctl", "monitors", "-j"],
                             capture_output=True, text=True, timeout=3).stdout
        mons = json.loads(out)
        m = next((m for m in mons if m.get("focused")), mons[0])
        return int(m["width"]), int(m["height"])
    except Exception:
        pass
    try:
        r = tk._default_root
        return r.winfo_screenwidth(), r.winfo_screenheight()
    except Exception:
        return 1920, 1080


INTRO = [
    "Privet sin huyni",
    "XWDb: 0x03527737",
    "XWDb: 0x0266712",
    "XWDb: 0x02897593",
    "XWDb: 0x01447812",
    "XWDb: 0x0150974",
    "XWDb: 0x03873760",
    "XWDb: 0x0700882",
    "XWDb: 0x03803618",
    "Locked by @larpdecrypt  |  t.me/larpdecrypt",
    "",
    "CatCrypt lock xd:3",
    "",
    "   * system locked",
]

ASCII_CAT = r"""
        /\_____/\
       /  o   o  \
      ( ==  ^  == )
       )         (
      (           )
     ( (  )   (  ) )
    (__(__)___(__)__)
""".strip("\n")

BODY = ("Ваш компьютер заблокирован, а все имеющиеся диски и файлы на них "
        "зашифрованы хакерской группировкой P I D O R I. Любые действия, связанные "
        "с попыткой снятия блокировки нанесут непоправимый вред Вашему компьютеру "
        "и приведут к потере всех ваших файлов без возможности восстановления. "
        "При попытке снять блокировку все ваши данные будут выгружены в сеть и "
        "будет подана ransomware нагрузка на ваш процессор, что приведет к его "
        "неисправности.")


class CatLock:
    def __init__(self, root, windowed=False):
        self.root = root
        self.done = False
        self.sfx = Sfx()
        self.windowed = windowed

        root.title("System")
        root.configure(bg=BLACK)
        if windowed:
            gw, gh = 1100, 620
            root.geometry(f"{gw}x{gh}")
            root.minsize(800, 460)
        elif IS_WIN:
            gw, gh = root.winfo_screenwidth(), root.winfo_screenheight()
            root.attributes("-fullscreen", True)
            root.attributes("-topmost", True)
        else:
            gw, gh = monitor_size()
            root.geometry(f"{gw}x{gh}+0+0")
            root.attributes("-topmost", True)
            # настоящий фуллскрин Hyprland (иначе waybar остаётся сверху)
            root.after(500, self.hypr_fullscreen)
            root.after(1200, self.hypr_fullscreen)
            root.after(2600, lambda: self.hypr_fullscreen(fallback=True))

        self.W, self.H = gw, gh
        self.S = gh / 576.0

        self.serif = pick_font("Times New Roman", "Liberation Serif", "DejaVu Serif")
        self.mono = pick_font("JetBrains Mono", "Consolas", "DejaVu Sans Mono",
                              "Liberation Mono", "Courier New")

        # Esc больше не закрывает — только показывает "попытка снятия"
        root.bind_all("<Escape>", lambda e: self.warn_attempt())
        root.bind_all("<Control-w>", lambda e: self.warn_attempt())
        # аварийный выход, в интерфейсе не показан
        root.bind_all("<Control-q>", lambda e: self.quit())
        root.bind_all("<Control-m>", lambda e: self.toggle_sound())

        self.music_enabled = "--no-music" not in sys.argv

        self.intro = tk.Frame(root, bg=BLACK)
        self.intro.place(x=0, y=0, relwidth=1, relheight=1)
        self.build_intro()

        self.root.after(300, self.force_focus)
        self.root.after(1500, self.force_focus)
        if IS_WIN:
            self.root.after(700, self.ensure_fullscreen)
            self.root.after(2500, self.ensure_fullscreen)
        self.has_full = self.sfx.has("full")
        self.music_vol = 0.80 if self.has_full else 0.45
        self.root.after(1200, self.begin_show)

    def hypr_fullscreen(self, fallback=False):
        """Hyprland 0.57: настоящий fullscreen через Lua-диспетчер."""
        if IS_WIN or self.done:
            return
        is_fs = False
        try:
            out = subprocess.run(["hyprctl", "clients", "-j"],
                                 capture_output=True, text=True, timeout=3).stdout
            me = None
            for c in json.loads(out):
                if c.get("pid") == os.getpid():
                    me = c
                    break
            if me is not None:
                is_fs = me.get("fullscreen") == 2
                if not is_fs:
                    try:
                        self.root.focus_force()
                    except Exception:
                        pass
                    subprocess.run(
                        ["hyprctl", "eval",
                         'hl.dispatch(hl.dsp.window.fullscreen({mode="fullscreen"}))'],
                        capture_output=True, timeout=3)
        except Exception:
            pass
        if not is_fs and fallback:
            # не Hyprland или диспетчер не сработал — растягиваем руками
            try:
                self.root.overrideredirect(True)
                self.root.geometry(f"{self.W}x{self.H}+0+0")
                self.root.attributes("-topmost", True)
                self.root.lift()
            except Exception:
                pass

    def ensure_fullscreen(self):
        """Если -fullscreen не сработал (Wine, странный DPI) — растягиваем вручную."""
        if self.done:
            return
        try:
            sw = self.root.winfo_screenwidth()
            sh = self.root.winfo_screenheight()
            w = self.root.winfo_width()
            h = self.root.winfo_height()
            if w < sw - 8 or h < sh - 8:
                self.root.overrideredirect(True)
                self.root.geometry(f"{sw}x{sh}+0+0")
                self.root.attributes("-topmost", True)
                self.root.lift()
                self.root.focus_force()
        except Exception:
            pass

    def force_focus(self):
        """Чтобы окно точно поймало клавиатуру (особенно в Hyprland)."""
        try:
            self.root.lift()
            self.root.focus_force()
        except Exception:
            pass
        if IS_WIN:
            return
        try:
            out = subprocess.run(["hyprctl", "clients", "-j"],
                                 capture_output=True, text=True, timeout=3).stdout
            for c in json.loads(out):
                if c.get("pid") == os.getpid():
                    subprocess.run(["hyprctl", "dispatch", "focuswindow",
                                    f"address:{c['address']}"],
                                   capture_output=True, timeout=3)
                    break
        except Exception:
            pass

    def begin_show(self):
        """Пауза ~1.2 с чёрного экрана, потом звук и консоль одновременно."""
        if self.done:
            return
        if self.has_full:
            self.sfx.start_music(self.music_vol)
        else:
            self.sfx.play("alarm", 0.95)
        self.root.after(120, self.intro_step)

    # ------------------------------------------------ заставка
    def build_intro(self):
        s = self.S
        self.log_lines = []
        box = tk.Frame(self.intro, bg=BLACK)
        box.place(x=int(10 * s), y=int(12 * s), anchor="nw")
        for _ in INTRO:
            lb = tk.Label(box, text="", bg=BLACK, fg=MAG, font=(self.mono, max(8, int(10 * s))),
                          anchor="w", justify="left")
            lb.pack(anchor="w")
            self.log_lines.append(lb)

        try:
            if Image is None:
                raise RuntimeError("no pillow")
            img = Image.open(CAT_PNG)
            size = int(190 * s)
            h = size
            w = int(img.width * h / img.height)
            img = img.resize((w, h), Image.LANCZOS)
            self.cat_img = ImageTk.PhotoImage(img)
            self.cat_label = tk.Label(self.intro, image=self.cat_img, bg=BLACK, bd=0)
            self.cat_label.place(relx=0.5, rely=0.40, anchor="center")
        except Exception:
            self.cat_label = None

        tk.Label(self.intro, text="CatCrypt", bg=BLACK, fg=MAG,
                 font=(self.serif, max(12, int(26 * s)))).place(
            relx=0.5, rely=0.63, anchor="center")

    def intro_step(self):
        if self.done:
            return
        i = getattr(self, "intro_i", 0)
        if i >= len(INTRO):
            self.root.after(400, self.show_pink)
            return
        self.log_lines[i].config(text=INTRO[i])
        if "system locked" in INTRO[i] and not self.has_full:
            self.sfx.play("beep", 1.0)
        self.intro_i = i + 1
        self.root.after(230, self.intro_step)

    # ------------------------------------------------ розовый экран с артом
    def show_pink(self):
        if self.done:
            return
        if Image is None:
            self.show_lock()
            return
        try:
            self.intro.destroy()
        except tk.TclError:
            pass
        self.pink = tk.Frame(self.root, bg=MAG_BRIGHT)
        self.pink.place(x=0, y=0, relwidth=1, relheight=1)
        try:
            img = Image.open(PINK_PNG).convert("RGB")
            w = self.W
            h = int(w * img.height / img.width)
            if h > self.H:
                h = self.H
                w = int(h * img.width / img.height)
            img = img.resize((w, h), Image.LANCZOS)
            self.pink_img = ImageTk.PhotoImage(img)
            tk.Label(self.pink, image=self.pink_img, bg=MAG_BRIGHT, bd=0).place(
                relx=0.5, rely=0.5, anchor="center")
        except Exception:
            pass
        self.root.after(1300, self.show_lock)

    # ------------------------------------------------ локер
    def show_lock(self):
        if self.done:
            return
        for f in (getattr(self, "intro", None), getattr(self, "pink", None)):
            try:
                f.destroy()
            except Exception:
                pass
        s = self.S
        w, h = self.W, self.H

        self.main = tk.Frame(self.root, bg=BLACK)
        self.main.place(x=0, y=0, relwidth=1, relheight=1)

        # часы
        self.clock = tk.Label(self.main, text="", bg=BLACK, fg="#c020c0",
                              font=(self.mono, max(9, int(11 * s))))
        self.clock.place(x=w - int(18 * s), y=int(18 * s), anchor="ne")
        self.tick_clock()

        # центральная колонка
        col_w = int(min(w * 0.46, 760 * s))
        left = (w - col_w) // 2
        top = int(h * 0.30)
        col = tk.Frame(self.main, bg=BLACK)
        col.place(x=left, y=top, width=col_w)

        # заголовочная полоса
        tk.Label(col, text="Ваши файлы зашифрованы", bg=MAG_BAR, fg="#100010",
                 font=(self.serif, max(7, int(9 * s))), bd=0,
                 ).pack(fill="x", ipady=max(1, int(1 * s)))

        # рамка
        frame = tk.Frame(col, bg=MAG)
        frame.pack(fill="x", pady=(int(2 * s), 0))
        inner = tk.Frame(frame, bg=BLACK)
        inner.pack(fill="both", expand=True, padx=max(1, int(s)), pady=max(1, int(s)))

        pad = int(7 * s)
        tk.Label(inner, text=BODY, bg=BLACK, fg=MAG, justify="left",
                 anchor="w", wraplength=col_w - 2 * pad,
                 font=(self.serif, max(8, int(10 * s))),
                 ).pack(fill="x", padx=pad, pady=(pad, int(5 * s)))

        row = tk.Frame(inner, bg=BLACK)
        row.pack(fill="x", padx=pad, pady=(0, int(4 * s)))
        f_contact = (self.serif, max(8, int(10 * s)))
        tk.Label(row, text="Уёбок ты пиши", bg=BLACK, fg=MAG, font=f_contact).pack(side="left")
        tk.Label(row, text="(тт)", bg=BLACK, fg=MAG, font=f_contact).pack(side="right")
        tk.Label(row, text="@larpdecrypt ", bg=BLACK, fg=MAG, font=f_contact).pack(side="right")

        tk.Label(col, text="Введите код разблокировки:", bg=BLACK, fg=MAG,
                 font=(self.serif, max(8, int(10 * s))),
                 ).pack(pady=(int(9 * s), int(3 * s)))

        self.entry = tk.Entry(col, bg=MAG_BRIGHT, fg=BLACK, insertbackground=BLACK,
                              relief="flat", bd=0, justify="left",
                              font=(self.serif, max(9, int(11 * s))),
                              highlightthickness=0)
        self.entry.pack(fill="x", ipady=max(2, int(2 * s)))
        self.entry.bind("<Return>", lambda e: self.unlock())
        self.entry.bind("<Key>", lambda e: self.sfx.play("type", 0.5))
        self.entry.focus_set()

        # низ экрана
        f_small = (self.mono, max(7, int(9 * s)))
        tk.Label(self.main, text="Current PC: 37DD4A47-39AF-4", bg=BLACK, fg=MAG_DIM,
                 font=f_small).place(x=int(12 * s), y=h - int(34 * s), anchor="w")
        tk.Label(self.main, text="[Enter]", bg=BLACK, fg=MAG_DIM,
                 font=f_small).place(x=w - int(12 * s), y=h - int(34 * s), anchor="e")
        tk.Label(self.main, text="ID: 34-F2D34A82-40FDE", bg=BLACK, fg=MAG_FAINT,
                 font=(self.mono, max(6, int(7 * s))),
                 ).place(x=int(12 * s), y=h - int(14 * s), anchor="w")

        self.root.after(150, self.force_focus)
        self.root.after(300, self.music_tick)

    def music_tick(self):
        if self.done:
            return
        if self.music_enabled and self.sfx.on:
            if IS_WIN:
                if not self.sfx.music_proc:
                    self.sfx.start_music(self.music_vol)
            else:
                p = self.sfx.music_proc
                if p is None or p.poll() is not None:
                    self.sfx.start_music(self.music_vol)
        self.root.after(1000, self.music_tick)

    def toggle_sound(self):
        self.sfx.on = not self.sfx.on
        if not self.sfx.on:
            self.sfx.stop_music()
        self.music_enabled = self.sfx.on

    def tick_clock(self):
        if self.done:
            return
        try:
            self.clock.config(text=time.strftime("%H:%M:%S"))
        except tk.TclError:
            return
        self.root.after(500, self.tick_clock)

    # ------------------------------------------------ попытка снять блокировку
    def warn_attempt(self):
        if self.done or not hasattr(self, "main"):
            return
        self.sfx.play("alarm", 1.0)
        if getattr(self, "popup", None) is not None:
            try:
                self.popup.destroy()
            except tk.TclError:
                pass
        s = self.S
        p = tk.Frame(self.main, bg=BLACK, highlightbackground=MAG,
                     highlightthickness=max(1, int(s)))
        inner = tk.Frame(p, bg=MAG_BAR)
        inner.pack(fill="x")
        tk.Label(inner, text="CatCrypt", bg=MAG_BAR, fg="#100010",
                 font=(self.serif, max(7, int(9 * s)))).pack()
        tk.Label(p, text="Замечена и остановлена\nпопытка снять блокировку!",
                 bg=BLACK, fg=MAG, font=(self.serif, max(8, int(10 * s))),
                 justify="center").pack(padx=int(22 * s), pady=int(14 * s))
        p.place(relx=0.5, rely=0.52, anchor="center")
        p.lift()
        self.popup = p
        self.root.after(2600, self.hide_popup)

    def hide_popup(self):
        p = getattr(self, "popup", None)
        if p is not None:
            try:
                p.destroy()
            except tk.TclError:
                pass
            self.popup = None

    # ------------------------------------------------ разблокировка
    def unlock(self):
        if self.done:
            return
        self.sfx.stop_music()
        self.sfx.play("chime", 0.9)
        self.done = True
        try:
            self.entry.config(state="disabled")
        except tk.TclError:
            return
        done = tk.Label(self.main, text="код принят · снимаем блокировку", bg=BLACK,
                        fg=MAG_BRIGHT, font=(self.serif, max(10, int(14 * self.S))))
        done.place(relx=0.5, rely=0.8, anchor="center")
        self.root.after(1200, self.quit)

    def quit(self):
        self.done = True
        self.sfx.stop_music()
        try:
            self.root.destroy()
        except tk.TclError:
            pass


def main():
    windowed = "--windowed" in sys.argv
    root = tk.Tk()
    app = CatLock(root, windowed=windowed)

    def bye(*_):
        # чтобы музыка не осталась играть, если процесс убили снаружи
        app.sfx.stop_music()
        os._exit(0)

    # SIGHUP есть только на linux, поэтому берём по имени
    for name in ("SIGINT", "SIGTERM", "SIGHUP", "SIGBREAK"):
        sig = getattr(signal, name, None)
        if sig is None:
            continue
        try:
            signal.signal(sig, bye)
        except Exception:
            pass

    try:
        root.mainloop()
    finally:
        app.sfx.stop_music()


if __name__ == "__main__":
    main()
