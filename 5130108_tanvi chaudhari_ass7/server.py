"""
server.py - Secure Multi-Client TCP Chat Server
Assignment 7: Secure Network Application Development Using TCP

Reuses the networking core of Assignment 6 (multi-client TCP server using
threading) and extends it with:
    Task 1 - Username / password authentication
    Task 2 - SHA-256 password hashing (no plaintext ever stored)
    Task 3 - Duplicate login prevention
    Task 4 - Input validation
    Task 5 - Failed login protection (5 attempts -> temporary block)
    Task 6 - Session management (logout, inactivity timeout) & secure logging

Networking logic is kept independent of any GUI so it can be reused by any
client (the Tkinter GUI in client_gui.py, or a simple CLI client).
"""

import socket
import threading
import hashlib
import csv
import os
import re
import time
from datetime import datetime

# --------------------------------------------------------------------------
# Configuration
# --------------------------------------------------------------------------
HOST = "0.0.0.0"
PORT = 5000

USERS_FILE = "users.csv"
LOG_FILE = "security_log.txt"

MAX_MESSAGE_SIZE = 1024          # bytes, Task 4
USERNAME_REGEX = re.compile(r"^[A-Za-z0-9_]{3,20}$")   # Task 4
MAX_FAILED_ATTEMPTS = 5          # Task 5
BLOCK_DURATION_SECONDS = 60      # Task 5
INACTIVITY_TIMEOUT_SECONDS = 120 # Task 6

SUPPORTED_COMMANDS = {"LOGIN", "MSG", "LOGOUT", "PING"}

# --------------------------------------------------------------------------
# Shared, thread-safe server state
# --------------------------------------------------------------------------
state_lock = threading.Lock()

active_users = {}          # username -> connection socket  (Task 3)
failed_attempts = {}       # username -> {"count": int, "blocked_until": float}
clients = {}                # conn -> {"username":..., "last_active": ts, "addr":...}


# --------------------------------------------------------------------------
# Secure logging (Task 6) - never log passwords, plaintext or hashed
# --------------------------------------------------------------------------
def log_event(event_type, username, addr, detail=""):
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    ip = addr[0] if addr else "unknown"
    line = f"[{timestamp}] {event_type} | user={username} | ip={ip} | {detail}\n"
    with state_lock:
        with open(LOG_FILE, "a") as f:
            f.write(line)
    print(line, end="")


# --------------------------------------------------------------------------
# User database helpers (Task 2 - SHA-256 hashing)
# --------------------------------------------------------------------------
def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def load_users():
    users = {}
    if not os.path.exists(USERS_FILE):
        return users
    with open(USERS_FILE, newline="") as f:
        reader = csv.reader(f)
        for row in reader:
            if len(row) >= 2:
                username, hashed = row[0].strip(), row[1].strip()
                users[username] = hashed
    return users


USERS = load_users()


# --------------------------------------------------------------------------
# Input validation (Task 4)
# --------------------------------------------------------------------------
def is_valid_username(username: str) -> bool:
    return bool(USERNAME_REGEX.match(username or ""))


def is_valid_password(password: str) -> bool:
    return bool(password) and len(password) <= 128


def is_valid_message(message: str) -> bool:
    return 0 < len(message.encode("utf-8")) <= MAX_MESSAGE_SIZE


def is_supported_command(cmd: str) -> bool:
    return cmd in SUPPORTED_COMMANDS


# --------------------------------------------------------------------------
# Failed login protection (Task 5)
# --------------------------------------------------------------------------
def is_blocked(username):
    record = failed_attempts.get(username)
    if not record:
        return False, 0
    if record["blocked_until"] and time.time() < record["blocked_until"]:
        return True, int(record["blocked_until"] - time.time())
    return False, 0


def register_failed_attempt(username):
    record = failed_attempts.setdefault(username, {"count": 0, "blocked_until": 0})
    record["count"] += 1
    if record["count"] >= MAX_FAILED_ATTEMPTS:
        record["blocked_until"] = time.time() + BLOCK_DURATION_SECONDS
        record["count"] = 0  # reset counter once block is applied


def clear_failed_attempts(username):
    if username in failed_attempts:
        failed_attempts[username] = {"count": 0, "blocked_until": 0}


# --------------------------------------------------------------------------
# Client handling
# --------------------------------------------------------------------------
def send_line(conn, text):
    try:
        conn.sendall((text + "\n").encode("utf-8"))
    except OSError:
        pass


def broadcast(text, exclude_conn=None):
    with state_lock:
        targets = [c for c in clients if c is not exclude_conn]
    for c in targets:
        send_line(c, text)


def authenticate(conn, addr, username, password):
    # Validate input first (Task 4)
    if not is_valid_username(username):
        log_event("INVALID_INPUT", username or "?", addr, "invalid username format")
        return False, "ERROR|Invalid username format"

    if not is_valid_password(password):
        log_event("INVALID_INPUT", username, addr, "empty or oversized password")
        return False, "ERROR|Password cannot be empty"

    # Failed-login block check (Task 5)
    blocked, remaining = is_blocked(username)
    if blocked:
        log_event("LOGIN_BLOCKED", username, addr, f"{remaining}s remaining")
        return False, f"ERROR|Account temporarily locked. Try again in {remaining}s"

    # Duplicate login prevention (Task 3)
    with state_lock:
        already_logged_in = username in active_users

    if already_logged_in:
        log_event("DUPLICATE_LOGIN", username, addr, "rejected - already logged in")
        return False, "ERROR|User already logged in elsewhere"

    # Credential check (Task 1 + Task 2, hashed comparison only)
    stored_hash = USERS.get(username)
    if stored_hash is None or stored_hash != hash_password(password):
        register_failed_attempt(username)
        log_event("LOGIN_FAILED", username, addr, "invalid credentials")
        return False, "ERROR|Invalid username or password"

    # Success
    clear_failed_attempts(username)
    with state_lock:
        active_users[username] = conn
        clients[conn]["username"] = username
        clients[conn]["last_active"] = time.time()
    log_event("LOGIN_SUCCESS", username, addr, "authenticated")
    return True, "OK|LOGIN_SUCCESS"


def logout(conn, addr, reason="client requested"):
    with state_lock:
        info = clients.get(conn)
        username = info["username"] if info else None
        if username and username in active_users:
            del active_users[username]
        if conn in clients:
            clients[conn]["username"] = None

    if username:
        log_event("LOGOUT", username, addr, reason)
        broadcast(f"SYS|{username} has left the chat", exclude_conn=conn)


def handle_client(conn, addr):
    clients[conn] = {"username": None, "last_active": time.time(), "addr": addr}
    log_event("CONNECT", "-", addr, "new TCP connection")
    buffer = ""

    try:
        conn.settimeout(5.0)
        while True:
            try:
                chunk = conn.recv(4096)
            except socket.timeout:
                # check inactivity timeout (Task 6)
                info = clients.get(conn)
                if info and info["username"]:
                    idle = time.time() - info["last_active"]
                    if idle > INACTIVITY_TIMEOUT_SECONDS:
                        send_line(conn, "ERROR|Session timed out due to inactivity")
                        log_event("SESSION_TIMEOUT", info["username"], addr,
                                  f"idle {int(idle)}s")
                        logout(conn, addr, reason="inactivity timeout")
                        break
                continue

            if not chunk:
                break

            buffer += chunk.decode("utf-8", errors="replace")
            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                line = line.strip()
                if not line:
                    continue
                process_message(conn, addr, line)
    except (ConnectionResetError, OSError):
        pass
    finally:
        info = clients.get(conn)
        if info and info["username"]:
            logout(conn, addr, reason="connection closed")
        with state_lock:
            clients.pop(conn, None)
        conn.close()
        log_event("DISCONNECT", "-", addr, "connection closed")


def process_message(conn, addr, line):
    parts = line.split("|")
    cmd = parts[0].strip().upper()

    # Reject unsupported commands (Task 4)
    if not is_supported_command(cmd):
        send_line(conn, "ERROR|Unsupported command")
        log_event("INVALID_INPUT", clients.get(conn, {}).get("username") or "-",
                   addr, f"unsupported command '{cmd}'")
        return

    info = clients.get(conn, {})

    if cmd == "LOGIN":
        if info.get("username"):
            send_line(conn, "ERROR|Already logged in")
            return
        username = parts[1].strip() if len(parts) > 1 else ""
        password = parts[2] if len(parts) > 2 else ""
        ok, response = authenticate(conn, addr, username, password)
        send_line(conn, response)
        if ok:
            broadcast(f"SYS|{username} has joined the chat", exclude_conn=conn)
        return

    # Everything below requires an authenticated session
    username = info.get("username")
    if not username:
        send_line(conn, "ERROR|Not authenticated")
        return

    # refresh activity timestamp (Task 6)
    with state_lock:
        clients[conn]["last_active"] = time.time()

    if cmd == "PING":
        send_line(conn, "OK|PONG")
        return

    if cmd == "LOGOUT":
        send_line(conn, "OK|LOGOUT_SUCCESS")
        logout(conn, addr, reason="client requested")
        return

    if cmd == "MSG":
        text = parts[1] if len(parts) > 1 else ""
        if not is_valid_message(text):
            send_line(conn, "ERROR|Message empty or too large (max 1024 bytes)")
            log_event("INVALID_INPUT", username, addr, "oversized/empty message")
            return
        log_event("MESSAGE", username, addr, "message relayed")
        broadcast(f"MSG|{username}|{text}", exclude_conn=conn)
        send_line(conn, "OK|MESSAGE_SENT")
        return


# --------------------------------------------------------------------------
# Server bootstrap
# --------------------------------------------------------------------------
def main():
    if not USERS:
        print(f"[WARN] No users loaded from {USERS_FILE}. "
              f"Run generate_users.py first to create accounts.")

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(5)
    print(f"[SERVER] Listening on {HOST}:{PORT}")
    log_event("SERVER_START", "-", ("0.0.0.0", 0), f"listening on port {PORT}")

    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down...")
        log_event("SERVER_STOP", "-", ("0.0.0.0", 0), "server shutdown")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
