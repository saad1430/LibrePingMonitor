import subprocess
import time
import platform
import threading
import os
import json
import sys
from datetime import datetime
import tkinter as tk
from tkinter import ttk, filedialog, scrolledtext
from plyer import notification
import ctypes

# ----------------------- CONFIG -----------------------
CONFIG_DIR = "config"
CONFIG_FILE = os.path.join(CONFIG_DIR, "settings.json")
LOGS_DIR = "logs"
DEFAULT_IP = "127.0.0.1"
DEFAULT_THRESHOLD = 20
DEFAULT_ULTIMATE_THRESHOLD = 100
monitoring = False
FAIL_THRESHOLD = 5

# Color tags for console highlighting
COLOR_TAGS = {
    "ok": {"foreground": "#4CAF50"},        # Green
    "high": {"foreground": "#FFC107"},     # Amber
    "critical": {"foreground": "#FF5722"}, # Deep Orange
    "lost": {"foreground": "#F44336"}      # Red
}

# ----------------------- STORAGE -----------------------
def ensure_config():
    if not os.path.exists(CONFIG_DIR):
        os.makedirs(CONFIG_DIR)
    if not os.path.exists(CONFIG_FILE):
        with open(CONFIG_FILE, 'w') as f:
            json.dump({
                "ips": [],
                "ui_state": {"geometry": "800x800", "maximized": False},
                "theme": "dark",
                "log_enabled": True,
                "threshold": DEFAULT_THRESHOLD,
                "ultimate_threshold": DEFAULT_ULTIMATE_THRESHOLD,
                "lost_packet_threshold": FAIL_THRESHOLD,
                "mute_high": False,
                "mute_critical_beep": False,
                "mute_critical_notify": False
            }, f)

def load_settings():
    ensure_config()
    with open(CONFIG_FILE, 'r') as f:
        return json.load(f)

def save_settings(settings):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(settings, f)

settings = load_settings()

# ----------------------- LOGGING -----------------------
def write_log(ip, message):
    if not os.path.exists(LOGS_DIR):
        os.makedirs(LOGS_DIR)
    filename = os.path.join(LOGS_DIR, f"{datetime.now().date()}__{ip}.log")
    with open(filename, 'a', encoding='utf-8') as f:
        f.write(message + "\n")

# ----------------------- ALERTS -----------------------
def beep():
    if platform.system() == "Windows":
        import winsound
        winsound.Beep(1000, 500)
    else:
        print("\a")

def alert(title, message):
    try:
        notification.notify(title=title, message=message, timeout=5)
    except:
        pass

def flash_taskbar():
    if platform.system() == "Windows":
        try:
            user32 = ctypes.windll.user32
            hwnd = user32.GetForegroundWindow()  # fallback
            try:
                # More accurate HWND using the window title
                hwnd = user32.FindWindowW(None, app.title())
            except:
                pass

            class FLASHWINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint),
                            ("hwnd", ctypes.c_void_p),
                            ("dwFlags", ctypes.c_uint),
                            ("uCount", ctypes.c_uint),
                            ("dwTimeout", ctypes.c_uint)]

            FLASHW_ALL = 3
            info = FLASHWINFO(ctypes.sizeof(FLASHWINFO), hwnd, FLASHW_ALL, 5, 0)
            user32.FlashWindowEx(ctypes.byref(info))
        except Exception as e:
            print("Taskbar flashing failed:", e)


# ----------------------- PING LOGIC -----------------------
def ping_once(host):
    try:
        result = subprocess.run(["ping", "-n", "1", host], capture_output=True, text=True, timeout=3)
        output = result.stdout
        if "Request timed out" in output or "Destination host unreachable" in output:
            return None
        elif "time=" in output:
            time_str = output.split("time=")[-1].split("ms")[0].strip()
            return int(time_str)
    except:
        return None

def start_monitoring(ip, threshold, ultimate_threshold, output_box, fail_threshold):
    global monitoring
    if monitoring:
        return
    monitoring = True
    if ip not in settings["ips"]:
        settings["ips"].append(ip)
        save_settings(settings)
    insert_colored_text(output_box, f"\n📡 Monitoring {ip} with threshold {threshold}ms (Ultimate: {ultimate_threshold}ms)\n", "ok")
    fail_count = 0

    while monitoring:
        latency = ping_once(ip)
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        log_to_file = log_var.get()

        if latency is None:
            msg = f"[{now}] ❌ Packet Lost!"
            tag = "lost"
            fail_count += 1
            flash_taskbar()
            if not settings.get("mute_critical_beep", False):
                beep()
            if not settings.get("mute_critical_notify", False):
                alert("Ping Monitor", f"❌ Lost ping to {ip} at {now}")
            if fail_count >= fail_threshold:
                msg += f" [FAILED {fail_threshold}x — Monitoring stopped]"
                monitoring = False
        elif latency > ultimate_threshold:
            fail_count = 0
            msg = f"[{now}] 🚨 CRITICAL Ping: {latency}ms"
            tag = "critical"
            if not settings.get("mute_critical_beep", False):
                beep()
            if not settings.get("mute_critical_notify", False):
                alert("Ping Monitor", f"🚨 CRITICAL Ping: {latency}ms to {ip} at {now}")
        elif latency > threshold:
            fail_count = 0
            msg = f"[{now}] ⚠️ High Ping: {latency}ms"
            tag = "high"
            if not settings.get("mute_high", False):
                beep()
        else:
            fail_count = 0
            msg = f"[{now}] ✅ Ping OK: {latency}ms"
            tag = "ok"

        insert_colored_text(output_box, msg + "\n", tag)
        if log_to_file:
            write_log(ip, msg)
        time.sleep(1)

def insert_colored_text(widget, text, tag):
    widget.config(state=tk.NORMAL)
    widget.insert(tk.END, text, tag)
    widget.config(state=tk.DISABLED)
    widget.see(tk.END)

# ----------------------- GUI SETUP -----------------------
def stop_monitoring():
    global monitoring
    monitoring = False

def clear_log_gui():
    output_box.config(state=tk.NORMAL)
    output_box.delete('1.0', tk.END)
    output_box.config(state=tk.DISABLED)

def export_log():
    content = output_box.get('1.0', tk.END)
    now = datetime.now().strftime("%Y-%m-%d")
    ip = ip_combo.get().replace(".", "_")
    default_name = f"{now}__{ip}.log"
    file = filedialog.asksaveasfilename(initialfile=default_name, defaultextension=".log", filetypes=[("Log files", "*.log"), ("Text files", "*.txt")])
    if file:
        with open(file, 'w', encoding='utf-8') as f:
            f.write(content)

def toggle_theme():
    settings["theme"] = "light" if settings["theme"] == "dark" else "dark"
    save_settings(settings)
    app.destroy()
    os.execl(sys.executable, sys.executable, *sys.argv)

app = tk.Tk()
app.title("LibrePingMonitor")
app.geometry(settings["ui_state"]["geometry"])
if settings["ui_state"]["maximized"]:
    app.state('zoomed')

is_dark = settings.get("theme", "dark") == "dark"

bg_color = "#1e1e1e" if is_dark else "#ffffff"
fg_color = "white" if is_dark else "black"
entry_bg = "#2e2e2e" if is_dark else "white"

app.configure(bg=bg_color)
style = ttk.Style()
style.theme_use("default")
style.configure("TLabel", background=bg_color, foreground=fg_color)
style.configure("TButton", background=entry_bg, foreground=fg_color)
style.configure("TCheckbutton", background=bg_color, foreground=fg_color)
style.configure("TCombobox", fieldbackground=entry_bg, background=entry_bg, foreground=fg_color)

stored_ips = settings["ips"]

tk.Label(app, text="Select or Enter IP Address:", bg=bg_color, fg=fg_color).pack()
ip_combo = ttk.Combobox(app, values=stored_ips, width=50)
ip_combo.set(stored_ips[0] if stored_ips else DEFAULT_IP)
ip_combo.pack()

tk.Label(app, text="Latency Threshold (ms):", bg=bg_color, fg=fg_color).pack()
thresh_entry = tk.Entry(app, bg=entry_bg, fg=fg_color, insertbackground=fg_color)
thresh_entry.insert(0, str(settings.get("threshold", DEFAULT_THRESHOLD)))
thresh_entry.pack()

tk.Label(app, text="Ultimate Threshold (ms):", bg=bg_color, fg=fg_color).pack()
ultimate_thresh_entry = tk.Entry(app, bg=entry_bg, fg=fg_color, insertbackground=fg_color)
ultimate_thresh_entry.insert(0, str(settings.get("ultimate_threshold", DEFAULT_ULTIMATE_THRESHOLD)))
ultimate_thresh_entry.pack()

lost_thresh_label = tk.Label(app, text="Lost Packet Threshold (before stop):", bg=bg_color, fg=fg_color)
lost_thresh_label.pack()
lost_thresh_entry = tk.Entry(app, bg=entry_bg, fg=fg_color, insertbackground=fg_color)
lost_thresh_entry.insert(0, str(settings.get("lost_packet_threshold", 5)))
lost_thresh_entry.pack()

log_var = tk.BooleanVar(value=settings.get("log_enabled", True))
def update_log_setting():
    settings["log_enabled"] = log_var.get()
    save_settings(settings)

tk.Checkbutton(app, text="Save logs to file", variable=log_var, command=update_log_setting, bg=bg_color, fg=fg_color, selectcolor=entry_bg).pack(pady=5)

mute_high_var = tk.BooleanVar(value=settings.get("mute_high", False))
def update_mute_high():
    settings["mute_high"] = mute_high_var.get()
    save_settings(settings)

tk.Checkbutton(app, text="Mute High Ping Beep", variable=mute_high_var, command=update_mute_high, bg=bg_color, fg=fg_color, selectcolor=entry_bg).pack()

mute_critical_beep_var = tk.BooleanVar(value=settings.get("mute_critical_beep", False))
def update_mute_critical_beep():
    settings["mute_critical_beep"] = mute_critical_beep_var.get()
    save_settings(settings)

tk.Checkbutton(app, text="Mute Critical Beep", variable=mute_critical_beep_var, command=update_mute_critical_beep, bg=bg_color, fg=fg_color, selectcolor=entry_bg).pack()

mute_critical_notify_var = tk.BooleanVar(value=settings.get("mute_critical_notify", False))
def update_mute_critical_notify():
    settings["mute_critical_notify"] = mute_critical_notify_var.get()
    save_settings(settings)

tk.Checkbutton(app, text="Mute Critical Notification", variable=mute_critical_notify_var, command=update_mute_critical_notify, bg=bg_color, fg=fg_color, selectcolor=entry_bg).pack()

output_box = scrolledtext.ScrolledText(app, height=20, bg=bg_color, fg=fg_color, insertbackground=fg_color)
output_box.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
output_box.config(state=tk.DISABLED)
output_box.bind("<Key>", lambda e: "break")

# Define text tags for colors
for tag, style_dict in COLOR_TAGS.items():
    output_box.tag_config(tag, **style_dict)

btn_frame = tk.Frame(app, bg=bg_color)
btn_frame.pack(pady=10)

def start_threaded_monitor():
    if monitoring:
        return
    settings["threshold"] = int(thresh_entry.get())
    settings["ultimate_threshold"] = int(ultimate_thresh_entry.get())
    settings["lost_packet_threshold"] = int(lost_thresh_entry.get())
    save_settings(settings)
    threading.Thread(
        target=start_monitoring,
        args=(
            ip_combo.get(),
            settings["threshold"],
            settings["ultimate_threshold"],
            output_box,
            settings["lost_packet_threshold"]
        ),
        daemon=True
    ).start()

tk.Button(btn_frame, text="Start Monitoring", command=start_threaded_monitor).grid(row=0, column=0, padx=5)
tk.Button(btn_frame, text="Stop Monitoring", command=stop_monitoring).grid(row=0, column=1, padx=5)
tk.Button(btn_frame, text="Clear Log", command=clear_log_gui).grid(row=0, column=2, padx=5)
tk.Button(btn_frame, text="Export Log", command=export_log).grid(row=0, column=3, padx=5)
tk.Button(btn_frame, text="Toggle Theme", command=toggle_theme).grid(row=0, column=4, padx=5)

def on_close():
    settings["ui_state"] = {"geometry": app.geometry(), "maximized": app.state() == 'zoomed'}
    save_settings(settings)
    app.destroy()

app.protocol("WM_DELETE_WINDOW", on_close)
app.mainloop()
