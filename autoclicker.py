import threading
import time
import ctypes
import tkinter as tk
import json
import os
import sys
from pynput import keyboard

# --- Win32 direct click ---
MOUSEEVENTF_LEFTDOWN = 0x0002
MOUSEEVENTF_LEFTUP = 0x0004
MOUSEEVENTF_RIGHTDOWN = 0x0008
MOUSEEVENTF_RIGHTUP = 0x0010
MOUSEEVENTF_MIDDLEDOWN = 0x0020
MOUSEEVENTF_MIDDLEUP = 0x0040

CLICK_MAP = {
    "Left":   (MOUSEEVENTF_LEFTDOWN, MOUSEEVENTF_LEFTUP),
    "Right":  (MOUSEEVENTF_RIGHTDOWN, MOUSEEVENTF_RIGHTUP),
    "Middle": (MOUSEEVENTF_MIDDLEDOWN, MOUSEEVENTF_MIDDLEUP),
}

def fast_click(button="Left"):
    down, up = CLICK_MAP[button]
    ctypes.windll.user32.mouse_event(down, 0, 0, 0, 0)
    ctypes.windll.user32.mouse_event(up, 0, 0, 0, 0)

# --- Force 1ms timer resolution ---
try:
    ctypes.windll.winmm.timeBeginPeriod(1)
except Exception:
    pass

# --- Settings path (next to .exe or .py) ---
def get_settings_path():
    if getattr(sys, 'frozen', False):
        base = os.path.dirname(sys.executable)
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    return os.path.join(base, "autoclicker_config.json")

DEFAULTS = {
    "cps": 20,
    "button": "Left",
    "hotkey": "l",
    "hotkey_display": "L",
}

def load_settings():
    try:
        with open(get_settings_path(), "r") as f:
            saved = json.load(f)
            for k, v in DEFAULTS.items():
                if k not in saved:
                    saved[k] = v
            return saved
    except Exception:
        return dict(DEFAULTS)

def save_settings(settings):
    try:
        with open(get_settings_path(), "w") as f:
            json.dump(settings, f)
    except Exception:
        pass


# --- Key name helper ---
def key_to_str(key):
    try:
        return key.char
    except AttributeError:
        name = str(key).replace("Key.", "")
        return name

def key_display(key):
    try:
        return key.char.upper()
    except AttributeError:
        name = str(key).replace("Key.", "")
        return name.capitalize()


class AutoClicker:
    def __init__(self):
        self.settings = load_settings()
        self.clicking = False
        self.target_cps = self.settings["cps"]
        self.delay = 1.0 / self.target_cps
        self.click_button = self.settings["button"]
        self.click_count = 0
        self.binding_hotkey = False

        self.hotkey_char = self.settings["hotkey"]
        self.hotkey_display = self.settings["hotkey_display"]

        # --- GUI ---
        self.root = tk.Tk()
        self.root.title("AutoClicker")
        self.root.geometry("260x380")
        self.root.resizable(False, False)
        self.root.configure(bg="#000000")
        self.root.attributes("-topmost", True)

        # --- title ---
        tk.Label(self.root, text="AUTOCLICKER", font=("Consolas", 15, "bold"),
                 bg="#000000", fg="#ffffff").pack(pady=(20, 0))

        # --- status ---
        self.status_var = tk.StringVar(value="OFF")
        self.status_label = tk.Label(self.root, textvariable=self.status_var,
                                     font=("Consolas", 22, "bold"), bg="#000000", fg="#555555")
        self.status_label.pack(pady=(2, 14))

        # --- CPS ---
        cps_frame = tk.Frame(self.root, bg="#000000")
        cps_frame.pack(fill="x", padx=28)

        self.speed_display = tk.StringVar(value=f"{self.target_cps} CPS")
        tk.Label(cps_frame, textvariable=self.speed_display,
                 font=("Consolas", 10), bg="#000000", fg="#aaaaaa").pack(anchor="w")

        self.speed_var = tk.IntVar(value=self.target_cps)
        tk.Scale(cps_frame, from_=1, to=500, orient="horizontal",
                 variable=self.speed_var, command=self.update_speed, showvalue=False,
                 bg="#111111", fg="#ffffff", highlightthickness=0,
                 troughcolor="#222222", activebackground="#ffffff",
                 sliderrelief="flat", bd=0, length=200).pack(fill="x", pady=(0, 6))

        # --- click button ---
        btn_frame = tk.Frame(self.root, bg="#000000")
        btn_frame.pack(fill="x", padx=28, pady=(0, 6))

        tk.Label(btn_frame, text="BUTTON", font=("Consolas", 9),
                 bg="#000000", fg="#555555").pack(anchor="w")

        self.btn_var = tk.StringVar(value=self.click_button)
        btn_row = tk.Frame(btn_frame, bg="#000000")
        btn_row.pack(anchor="w", pady=(2, 0))

        for btn_name in ["Left", "Right", "Middle"]:
            b = tk.Radiobutton(btn_row, text=btn_name, variable=self.btn_var, value=btn_name,
                                font=("Consolas", 9), bg="#000000", fg="#aaaaaa",
                                selectcolor="#000000", activebackground="#000000",
                                activeforeground="#ffffff", highlightthickness=0,
                                command=self.update_button)
            b.pack(side="left", padx=(0, 8))

        # --- hotkey ---
        hk_frame = tk.Frame(self.root, bg="#000000")
        hk_frame.pack(fill="x", padx=28, pady=(0, 6))

        tk.Label(hk_frame, text="HOTKEY", font=("Consolas", 9),
                 bg="#000000", fg="#555555").pack(anchor="w")

        hk_row = tk.Frame(hk_frame, bg="#000000")
        hk_row.pack(anchor="w", pady=(2, 0))

        self.hotkey_label = tk.Label(hk_row, text=self.hotkey_display,
                                     font=("Consolas", 11, "bold"), bg="#111111", fg="#ffffff",
                                     padx=10, pady=2)
        self.hotkey_label.pack(side="left")

        self.bind_btn = tk.Button(hk_row, text="Set", font=("Consolas", 9),
                                   bg="#222222", fg="#aaaaaa", bd=0, padx=8, pady=2,
                                   activebackground="#333333", activeforeground="#ffffff",
                                   cursor="hand2", command=self.start_binding)
        self.bind_btn.pack(side="left", padx=(6, 0))

        # --- actual cps ---
        self.actual_var = tk.StringVar(value="")
        tk.Label(self.root, textvariable=self.actual_var,
                 font=("Consolas", 9), bg="#000000", fg="#444444").pack(pady=(6, 0))

        # --- toggle button ---
        self.toggle_btn = tk.Button(self.root, text=f"START  [ {self.hotkey_display} ]",
                                     font=("Consolas", 12, "bold"),
                                     bg="#ffffff", fg="#000000",
                                     activebackground="#cccccc", activeforeground="#000000",
                                     bd=0, padx=20, pady=6, cursor="hand2",
                                     command=self.toggle)
        self.toggle_btn.pack(pady=(10, 18))

        # --- threads ---
        threading.Thread(target=self.click_loop, daemon=True).start()
        threading.Thread(target=self.measure_cps, daemon=True).start()

        self.kb_listener = keyboard.Listener(on_press=self.on_key)
        self.kb_listener.daemon = True
        self.kb_listener.start()

        self.root.protocol("WM_DELETE_WINDOW", self.quit_app)
        self.root.mainloop()

    # --- speed ---
    def update_speed(self, _=None):
        self.target_cps = self.speed_var.get()
        self.delay = 1.0 / self.target_cps
        self.speed_display.set(f"{self.target_cps} CPS")

    # --- button ---
    def update_button(self):
        self.click_button = self.btn_var.get()

    # --- hotkey binding ---
    def start_binding(self):
        self.binding_hotkey = True
        self.hotkey_label.configure(text="...", fg="#888888")
        self.bind_btn.configure(text="Press key")

    def finish_binding(self, key):
        self.hotkey_char = key_to_str(key)
        self.hotkey_display = key_display(key)
        self.hotkey_label.configure(text=self.hotkey_display, fg="#ffffff")
        self.bind_btn.configure(text="Set")
        self.toggle_btn.configure(text=f"START  [ {self.hotkey_display} ]")
        self.binding_hotkey = False

    # --- toggle ---
    def toggle(self):
        self.clicking = not self.clicking
        if self.clicking:
            self.click_count = 0
            self.status_var.set("ON")
            self.status_label.configure(fg="#ffffff")
            self.toggle_btn.configure(text=f"STOP  [ {self.hotkey_display} ]",
                                       bg="#000000", fg="#ffffff")
        else:
            self.status_var.set("OFF")
            self.status_label.configure(fg="#555555")
            self.toggle_btn.configure(text=f"START  [ {self.hotkey_display} ]",
                                       bg="#ffffff", fg="#000000")
            self.actual_var.set("")

    # --- click loop ---
    def click_loop(self):
        while True:
            if self.clicking:
                next_click = time.perf_counter() + self.delay
                fast_click(self.click_button)
                self.click_count += 1
                remaining = next_click - time.perf_counter()
                if remaining > 0.002:
                    time.sleep(remaining - 0.001)
                while time.perf_counter() < next_click:
                    pass
            else:
                time.sleep(0.05)

    # --- measure ---
    def measure_cps(self):
        while True:
            if self.clicking:
                start = self.click_count
                time.sleep(1.0)
                if self.clicking:
                    measured = self.click_count - start
                    self.actual_var.set(f"{measured} actual CPS  ·  {self.click_count:,} total")
            else:
                time.sleep(0.2)

    # --- key handler ---
    def on_key(self, key):
        if self.binding_hotkey:
            self.root.after(0, lambda: self.finish_binding(key))
            return

        pressed = key_to_str(key)
        if pressed == self.hotkey_char:
            self.root.after(0, self.toggle)

    # --- quit ---
    def quit_app(self):
        self.clicking = False
        self.settings["cps"] = self.target_cps
        self.settings["button"] = self.click_button
        self.settings["hotkey"] = self.hotkey_char
        self.settings["hotkey_display"] = self.hotkey_display
        save_settings(self.settings)
        try:
            ctypes.windll.winmm.timeEndPeriod(1)
        except Exception:
            pass
        self.root.destroy()
        import os; os._exit(0)

if __name__ == "__main__":
    AutoClicker()