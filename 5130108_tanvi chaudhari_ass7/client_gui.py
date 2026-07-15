"""
client_gui.py - Tkinter GUI client for the Secure Multi-Client TCP Chat
Assignment 7: Secure Network Application Development Using TCP

The GUI is kept strictly separate from the networking logic:
    - SecureChatClient  -> handles the socket/networking (reusable, no GUI code)
    - ChatApp            -> Tkinter GUI that calls into SecureChatClient

Reuses the GUI layout style from Assignment 6 and adds a login screen,
error banners for validation/blocking messages, and a logout button.
"""

import socket
import threading
import tkinter as tk
from tkinter import ttk, messagebox

HOST = "10.0.0.1"   # change to server IP when running across Mininet hosts
PORT = 5000


# --------------------------------------------------------------------------
# Networking layer (no GUI dependencies)
# --------------------------------------------------------------------------
class SecureChatClient:
    def __init__(self, host=HOST, port=PORT):
        self.host = host
        self.port = port
        self.sock = None
        self.connected = False
        self.on_message = None      # callback(text) set by GUI
        self._recv_thread = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect((self.host, self.port))
        self.connected = True
        self._recv_thread = threading.Thread(target=self._listen, daemon=True)
        self._recv_thread.start()

    def _listen(self):
        buffer = ""
        while self.connected:
            try:
                chunk = self.sock.recv(4096)
            except OSError:
                break
            if not chunk:
                break
            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if line and self.on_message:
                    self.on_message(line)
        self.connected = False

    def _send(self, text):
        if self.sock:
            self.sock.sendall((text + "\n").encode("utf-8"))

    def login(self, username, password):
        self._send(f"LOGIN|{username}|{password}")

    def send_message(self, text):
        self._send(f"MSG|{text}")

    def logout(self):
        self._send("LOGOUT")

    def close(self):
        self.connected = False
        if self.sock:
            try:
                self.sock.close()
            except OSError:
                pass


# --------------------------------------------------------------------------
# GUI layer
# --------------------------------------------------------------------------
class ChatApp:
    def __init__(self, root):
        self.root = root
        self.root.title("Secure TCP Chat")
        self.root.geometry("480x560")
        self.client = SecureChatClient()
        self.username = None

        self.login_frame = None
        self.chat_frame = None

        self.build_login_frame()

    # ---------------- Login screen ----------------
    def build_login_frame(self):
        self.login_frame = ttk.Frame(self.root, padding=30)
        self.login_frame.pack(expand=True, fill="both")

        ttk.Label(self.login_frame, text="Secure Chat Login",
                  font=("Segoe UI", 16, "bold")).pack(pady=(0, 20))

        ttk.Label(self.login_frame, text="Username").pack(anchor="w")
        self.username_entry = ttk.Entry(self.login_frame)
        self.username_entry.pack(fill="x", pady=(0, 10))

        ttk.Label(self.login_frame, text="Password").pack(anchor="w")
        self.password_entry = ttk.Entry(self.login_frame, show="*")
        self.password_entry.pack(fill="x", pady=(0, 20))
        self.password_entry.bind("<Return>", lambda e: self.attempt_login())

        self.status_label = ttk.Label(self.login_frame, text="", foreground="red")
        self.status_label.pack(pady=(0, 10))

        ttk.Button(self.login_frame, text="Login",
                   command=self.attempt_login).pack(fill="x")

    def attempt_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get()

        if not username or not password:
            self.status_label.config(text="Username and password are required")
            return

        try:
            if not self.client.connected:
                self.client.connect()
        except OSError as e:
            self.status_label.config(text=f"Cannot reach server: {e}")
            return

        self.client.on_message = self.handle_server_message
        self.pending_username = username
        self.client.login(username, password)

    # ---------------- Server message handling ----------------
    def handle_server_message(self, line):
        self.root.after(0, self._process_line, line)

    def _process_line(self, line):
        parts = line.split("|")
        tag = parts[0]

        if tag == "OK" and len(parts) > 1 and parts[1] == "LOGIN_SUCCESS":
            self.username = self.pending_username
            self.build_chat_frame()
            return

        if tag == "ERROR":
            msg = parts[1] if len(parts) > 1 else "Unknown error"
            if self.chat_frame is None:
                self.status_label.config(text=msg)
            else:
                self.append_chat(f"[SYSTEM] {msg}")
                if "timed out" in msg.lower():
                    self.return_to_login()
            return

        if tag == "MSG" and len(parts) >= 3:
            self.append_chat(f"{parts[1]}: {parts[2]}")
            return

        if tag == "SYS":
            self.append_chat(f"[SYSTEM] {parts[1] if len(parts) > 1 else ''}")
            return

    # ---------------- Chat screen ----------------
    def build_chat_frame(self):
        self.login_frame.destroy()
        self.chat_frame = ttk.Frame(self.root, padding=10)
        self.chat_frame.pack(expand=True, fill="both")

        top = ttk.Frame(self.chat_frame)
        top.pack(fill="x")
        ttk.Label(top, text=f"Logged in as {self.username}",
                  font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(top, text="Logout", command=self.do_logout).pack(side="right")

        self.chat_display = tk.Text(self.chat_frame, state="disabled", wrap="word")
        self.chat_display.pack(expand=True, fill="both", pady=10)

        bottom = ttk.Frame(self.chat_frame)
        bottom.pack(fill="x")
        self.message_entry = ttk.Entry(bottom)
        self.message_entry.pack(side="left", expand=True, fill="x")
        self.message_entry.bind("<Return>", lambda e: self.send_message())
        ttk.Button(bottom, text="Send", command=self.send_message).pack(side="right")

    def append_chat(self, text):
        self.chat_display.config(state="normal")
        self.chat_display.insert("end", text + "\n")
        self.chat_display.config(state="disabled")
        self.chat_display.see("end")

    def send_message(self):
        text = self.message_entry.get().strip()
        if not text:
            return
        if len(text.encode("utf-8")) > 1024:
            messagebox.showerror("Message too large", "Message exceeds 1024 bytes")
            return
        self.client.send_message(text)
        self.message_entry.delete(0, "end")

    def do_logout(self):
        self.client.logout()
        self.client.close()
        self.return_to_login()

    def return_to_login(self):
        if self.chat_frame:
            self.chat_frame.destroy()
            self.chat_frame = None
        self.client = SecureChatClient()
        self.build_login_frame()


def main():
    root = tk.Tk()
    app = ChatApp(root)

    def on_close():
        try:
            app.client.close()
        except Exception:
            pass
        root.destroy()

    root.protocol("WM_DELETE_WINDOW", on_close)
    root.mainloop()


if __name__ == "__main__":
    main()
