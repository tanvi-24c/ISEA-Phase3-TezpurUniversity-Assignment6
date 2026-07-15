"""
server.py
Assignment 6 - GUI-Based Multi-Client Chat Application Using TCP
Roll No: 5130108   Name: Tanvi Chaudhari

This server is reused (with minimal modification) from Assignment 5. It handles:
  - Client connections over TCP
  - Username-based login
  - Broadcast messaging
  - Private messaging
  - Online user list management
  - Join / leave notifications
  - Logging of all activity

Protocol: newline-delimited JSON messages. Each message is a JSON object
followed by "\n". This keeps the wire format simple and lets the GUI client
tell messages apart by a "type" field, e.g.:

    {"type": "login", "username": "alice"}
    {"type": "broadcast", "text": "hello everyone"}
    {"type": "private", "to": "bob", "text": "hi bob"}

Run:
    python3 server.py
"""

import socket
import threading
import json
import logging
from datetime import datetime

HOST = '0.0.0.0'
PORT = 5000

logging.basicConfig(
    filename='server.log',
    level=logging.INFO,
    format='%(asctime)s - %(message)s'
)

clients = {}          # username -> socket connection
clients_lock = threading.Lock()


def log(msg):
    print(msg)
    logging.info(msg)


def send_json(sock, obj):
    """Send one JSON message terminated by a newline."""
    try:
        data = (json.dumps(obj) + "\n").encode('utf-8')
        sock.sendall(data)
    except OSError:
        pass


def broadcast(obj, exclude=None):
    with clients_lock:
        targets = list(clients.items())
    for uname, sock in targets:
        if uname != exclude:
            send_json(sock, obj)


def broadcast_userlist():
    with clients_lock:
        users = list(clients.keys())
    broadcast({"type": "userlist", "users": users})


def handle_client(conn, addr):
    username = None
    buffer = ""
    try:
        while True:
            chunk = conn.recv(4096)
            if not chunk:
                break
            buffer += chunk.decode('utf-8', errors='ignore')

            while "\n" in buffer:
                line, buffer = buffer.split("\n", 1)
                if not line.strip():
                    continue
                try:
                    msg = json.loads(line)
                except json.JSONDecodeError:
                    continue

                mtype = msg.get("type")

                # ---------------- LOGIN ----------------
                if mtype == "login":
                    uname = (msg.get("username") or "").strip()
                    if not uname:
                        send_json(conn, {"type": "login_result", "success": False,
                                          "reason": "Username cannot be empty."})
                        continue

                    with clients_lock:
                        if uname in clients:
                            send_json(conn, {"type": "login_result", "success": False,
                                              "reason": "Username already taken."})
                            continue
                        clients[uname] = conn

                    username = uname
                    send_json(conn, {"type": "login_result", "success": True,
                                      "username": uname})
                    log(f"{uname} connected from {addr}")
                    broadcast({"type": "notice",
                               "text": f"{uname} has joined the chat."}, exclude=uname)
                    broadcast_userlist()

                # ---------------- BROADCAST ----------------
                elif mtype == "broadcast" and username:
                    text = msg.get("text", "")
                    log(f"[BROADCAST] {username}: {text}")
                    broadcast({
                        "type": "broadcast",
                        "from": username,
                        "text": text,
                        "time": datetime.now().strftime("%H:%M:%S")
                    })

                # ---------------- PRIVATE MESSAGE ----------------
                elif mtype == "private" and username:
                    to_user = msg.get("to")
                    text = msg.get("text", "")
                    log(f"[PRIVATE] {username} -> {to_user}: {text}")

                    with clients_lock:
                        target = clients.get(to_user)

                    payload = {
                        "type": "private",
                        "from": username,
                        "to": to_user,
                        "text": text,
                        "time": datetime.now().strftime("%H:%M:%S")
                    }
                    if target:
                        send_json(target, payload)
                        send_json(conn, payload)  # echo back so sender sees it too
                    else:
                        send_json(conn, {"type": "error",
                                          "text": f"User '{to_user}' not found or offline."})

                # ---------------- DISCONNECT ----------------
                elif mtype == "disconnect":
                    raise ConnectionResetError

    except (ConnectionResetError, ConnectionAbortedError, OSError):
        pass
    finally:
        if username:
            with clients_lock:
                clients.pop(username, None)
            log(f"{username} disconnected.")
            broadcast({"type": "notice", "text": f"{username} has left the chat."})
            broadcast_userlist()
        conn.close()


def main():
    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(10)
    log(f"Server listening on {HOST}:{PORT}")

    try:
        while True:
            conn, addr = server_sock.accept()
            t = threading.Thread(target=handle_client, args=(conn, addr), daemon=True)
            t.start()
    except KeyboardInterrupt:
        log("Server shutting down.")
    finally:
        server_sock.close()


if __name__ == "__main__":
    main()
