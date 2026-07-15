"""
client_gui.py
Assignment 6 - GUI-Based Multi-Client Chat Application Using TCP
Roll No: 5130108   Name: Tanvi Chaudhari

A Tkinter GUI wrapped around the Assignment 5 TCP socket client logic.
Networking is kept separate from GUI code: all socket send/receive happens
in ChatClient methods (send_json / recv_loop), while GUI widgets only ever
read from / write to a thread-safe queue.Queue, which the main thread polls
with root.after(). This keeps the GUI responsive even while messages are
being received in the background thread (Task 5 requirement).

Suggested widgets from Appendix A are used throughout:
Tk, Frame, Label, Entry, Button, Listbox, ScrolledText, Messagebox, StringVar/BooleanVar.

Run:
    python3 client_gui.py
"""

import socket
import threading
import json
import queue
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText


class ChatClient:
    def __init__(self, root):
        self.root = root
        self.root.title("Chat Client - Login")

        self.sock = None
        self.username = None
        self.connected = False
        self.recv_thread = None
        self.msg_queue = queue.Queue()

        self.build_login_frame()
        self.root.after(100, self.process_queue)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)

    # ==================== LOGIN WINDOW (Task 1) ====================
    def build_login_frame(self):
        self.login_frame = ttk.Frame(self.root, padding=24)
        self.login_frame.grid(row=0, column=0, sticky="nsew")
        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        ttk.Label(self.login_frame, text="Chat Login", font=("Segoe UI", 14, "bold")) \
            .grid(row=0, column=0, columnspan=2, pady=(0, 12))

        ttk.Label(self.login_frame, text="Server IP:").grid(row=1, column=0, sticky="w", pady=4)
        self.ip_entry = ttk.Entry(self.login_frame)
        self.ip_entry.insert(0, "127.0.0.1")
        self.ip_entry.grid(row=1, column=1, pady=4)

        ttk.Label(self.login_frame, text="Port:").grid(row=2, column=0, sticky="w", pady=4)
        self.port_entry = ttk.Entry(self.login_frame)
        self.port_entry.insert(0, "5000")
        self.port_entry.grid(row=2, column=1, pady=4)

        ttk.Label(self.login_frame, text="Username:").grid(row=3, column=0, sticky="w", pady=4)
        self.username_entry = ttk.Entry(self.login_frame)
        self.username_entry.grid(row=3, column=1, pady=4)

        ttk.Label(self.login_frame, text="Password (optional):").grid(row=4, column=0, sticky="w", pady=4)
        self.password_entry = ttk.Entry(self.login_frame, show="*")
        self.password_entry.grid(row=4, column=1, pady=4)

        self.connect_btn = ttk.Button(self.login_frame, text="Connect", command=self.on_connect)
        self.connect_btn.grid(row=5, column=0, columnspan=2, pady=14)

        self.login_status = ttk.Label(self.login_frame, text="", foreground="red")
        self.login_status.grid(row=6, column=0, columnspan=2)

        self.username_entry.bind("<Return>", lambda e: self.on_connect())
        self.password_entry.bind("<Return>", lambda e: self.on_connect())

    def on_connect(self):
        ip = self.ip_entry.get().strip()
        port_str = self.port_entry.get().strip()
        username = self.username_entry.get().strip()

        # ---- Input validation ----
        if not username:
            self.login_status.config(text="Username cannot be empty.")
            return
        if not ip or not port_str.isdigit():
            self.login_status.config(text="Enter a valid server IP and port.")
            return

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(5)
            self.sock.connect((ip, int(port_str)))
            self.sock.settimeout(None)
        except OSError as e:
            self.login_status.config(text=f"Connection failed: {e}")
            self.sock = None
            return

        self.username = username
        self.send_json({"type": "login", "username": username})

        # Background thread for receiving messages (Task 5)
        self.recv_thread = threading.Thread(target=self.recv_loop, daemon=True)
        self.recv_thread.start()

        self.connect_btn.config(state="disabled")
        self.login_status.config(text="Connecting...", foreground="blue")

    # ==================== NETWORKING (reused Assignment 5 logic) ====================
    def send_json(self, obj):
        if self.sock:
            try:
                self.sock.sendall((json.dumps(obj) + "\n").encode("utf-8"))
            except OSError:
                self.msg_queue.put({"type": "_disconnected"})

    def recv_loop(self):
        """Runs in a background thread. Never touches Tkinter widgets directly;
        it only pushes parsed messages onto the thread-safe queue."""
        buffer = ""
        try:
            while True:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                buffer += chunk.decode("utf-8", errors="ignore")
                while "\n" in buffer:
                    line, buffer = buffer.split("\n", 1)
                    if not line.strip():
                        continue
                    try:
                        msg = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    self.msg_queue.put(msg)
        except OSError:
            pass
        finally:
            self.msg_queue.put({"type": "_disconnected"})

    def process_queue(self):
        """Runs in the main GUI thread via root.after(); safe to update widgets here."""
        try:
            while True:
                msg = self.msg_queue.get_nowait()
                self.handle_message(msg)
        except queue.Empty:
            pass
        self.root.after(100, self.process_queue)

    # ==================== MESSAGE HANDLING ====================
    def handle_message(self, msg):
        mtype = msg.get("type")

        if mtype == "login_result":
            if msg.get("success"):
                self.build_chat_frame()
            else:
                self.connect_btn.config(state="normal")
                self.login_status.config(text=msg.get("reason", "Login failed."), foreground="red")
                if self.sock:
                    self.sock.close()
                    self.sock = None

        elif mtype == "broadcast":
            self.append_chat(f"[{msg.get('time','')}] {msg['from']}: {msg['text']}")

        elif mtype == "private":
            if msg["from"] == self.username:
                direction = f"you -> {msg['to']}"
            else:
                direction = f"{msg['from']} -> you"
            self.append_chat(f"[{msg.get('time','')}] (private) {direction}: {msg['text']}")

        elif mtype == "notice":
            self.append_chat(f"* {msg['text']} *")

        elif mtype == "userlist":
            self.update_userlist(msg.get("users", []))

        elif mtype == "error":
            self.append_chat(f"[ERROR] {msg['text']}")

        elif mtype == "_disconnected":
            was_connected = self.connected
            self.connected = False
            if hasattr(self, "status_label"):
                self.status_label.config(text="Disconnected", foreground="red")
            if was_connected:
                messagebox.showinfo("Disconnected", "Connection to server was closed.")

    # ==================== CHAT WINDOW (Task 2, 3, 4) ====================
    def build_chat_frame(self):
        self.connected = True
        self.login_frame.destroy()
        self.root.title(f"Chat Client - {self.username}")

        main = ttk.Frame(self.root, padding=8)
        main.grid(row=0, column=0, sticky="nsew")
        main.rowconfigure(0, weight=1)
        main.columnconfigure(0, weight=3)
        main.columnconfigure(1, weight=1)

        # ---- Scrollable chat display ----
        self.chat_area = ScrolledText(main, state="disabled", wrap="word", height=20, width=60)
        self.chat_area.grid(row=0, column=0, sticky="nsew", padx=(0, 8))

        # ---- Online users panel (Task 3) ----
        users_frame = ttk.LabelFrame(main, text="Online Users")
        users_frame.grid(row=0, column=1, sticky="nsew")
        self.user_listbox = tk.Listbox(users_frame)
        self.user_listbox.pack(fill="both", expand=True, padx=4, pady=4)

        # ---- Message input row ----
        input_frame = ttk.Frame(main)
        input_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        input_frame.columnconfigure(0, weight=1)

        self.msg_entry = ttk.Entry(input_frame)
        self.msg_entry.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.msg_entry.bind("<Return>", lambda e: self.on_send())
        self.msg_entry.focus_set()

        self.private_var = tk.BooleanVar(value=False)
        private_check = ttk.Checkbutton(input_frame, text="Private to selected user",
                                         variable=self.private_var)
        private_check.grid(row=0, column=1, padx=4)

        send_btn = ttk.Button(input_frame, text="Send", command=self.on_send)
        send_btn.grid(row=0, column=2, padx=4)

        disconnect_btn = ttk.Button(input_frame, text="Disconnect", command=self.on_disconnect)
        disconnect_btn.grid(row=0, column=3, padx=4)

        # ---- Status indicator ----
        self.status_label = ttk.Label(main, text=f"Connected as {self.username}", foreground="green")
        self.status_label.grid(row=2, column=0, columnspan=2, sticky="w", pady=(6, 0))

        self.root.rowconfigure(0, weight=1)
        self.root.columnconfigure(0, weight=1)

        self.append_chat(f"Welcome, {self.username}! You are connected.")

    def append_chat(self, text):
        self.chat_area.config(state="normal")
        self.chat_area.insert("end", text + "\n")
        self.chat_area.see("end")  # auto-scroll
        self.chat_area.config(state="disabled")

    def update_userlist(self, users):
        self.user_listbox.delete(0, "end")
        for u in users:
            label = f"{u} (you)" if u == self.username else u
            self.user_listbox.insert("end", label)

    def on_send(self):
        text = self.msg_entry.get().strip()
        if not text or not self.connected:
            return

        if self.private_var.get():
            sel = self.user_listbox.curselection()
            if not sel:
                messagebox.showwarning("No user selected", "Select a user to send a private message.")
                return
            target = self.user_listbox.get(sel[0]).replace(" (you)", "")
            if target == self.username:
                messagebox.showwarning("Invalid target", "You cannot private message yourself.")
                return
            self.send_json({"type": "private", "to": target, "text": text})
        else:
            self.send_json({"type": "broadcast", "text": text})

        self.msg_entry.delete(0, "end")

    def on_disconnect(self):
        if self.connected:
            self.send_json({"type": "disconnect"})
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass
        self.connected = False
        self.status_label.config(text="Disconnected", foreground="red")

    def on_close(self):
        try:
            self.on_disconnect()
        except Exception:
            pass
        self.root.destroy()


def main():
    root = tk.Tk()
    root.geometry("720x460")
    root.minsize(600, 400)
    ChatClient(root)
    root.mainloop()


if __name__ == "__main__":
    main()
