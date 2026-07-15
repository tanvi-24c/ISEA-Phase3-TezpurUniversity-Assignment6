# ISEA-Phase3-TezpurUniversity-Assignment6

## Project Title
GUI-Based Multi-Client Chat Application Using TCP

**Roll No:** 5130108
**Name:** Tanvi Chaudhari

## Objective
Convert the terminal-based TCP chat application from Assignment 5 into a graphical
desktop application using Tkinter, while reusing the existing server implementation
and socket communication logic. Introduces GUI programming, event-driven programming,
and multithreading for a responsive client.

## Software Requirements
- Python 3.8+
- Standard library only: `socket`, `threading`, `json`, `queue`, `tkinter`,
  `tkinter.ttk`, `tkinter.scrolledtext`
- Mininet (for network topology testing)
- Wireshark (for packet capture verification)

## Network Topology
```
sudo mn --topo single,5
```
| Host | Role          |
|------|---------------|
| h1   | Chat Server   |
| h2   | Client A      |
| h3   | Client B      |
| h4   | Client C      |
| h5   | Client D      |

Verify connectivity with `nodes`, `net`, and `pingall` inside the Mininet CLI.

## Execution Steps
1. On **h1** (server host):
   ```
   python3 server.py
   ```
2. On **h2–h5** (client hosts), run the GUI client on each:
   ```
   python3 client_gui.py
   ```
3. In the login window, enter:
   - Server IP (h1's IP inside Mininet)
   - Port `5000`
   - A unique username
   - Click **Connect**
4. Use the chat window to send broadcast messages, select a user and check
   "Private to selected user" to send a private message, and use **Disconnect**
   to leave the chat.
5. Capture traffic with Wireshark using filter `tcp.port == 5000` during
   connection, broadcast, private messaging, and disconnection.

## Implementation Summary
- **server.py**: Reused from Assignment 5. Accepts multiple TCP clients on
  separate threads, handles login, broadcast, private messaging, online user
  list broadcasts, join/leave notifications, and activity logging
  (`server.log`).
- **client_gui.py**: New GUI client built around the Assignment 5 socket logic.
  - **Login window**: server IP/port, username, optional password, input
    validation, and success/error feedback.
  - **Chat window**: scrollable message area (auto-scrolling), online users
    list, message entry with Send/Disconnect buttons, and a connection status
    label.
  - **Background thread**: a dedicated receive thread reads from the socket
    and pushes parsed messages onto a thread-safe `queue.Queue`; the main
    thread polls the queue via `root.after()` so the GUI never blocks on
    network I/O and remains responsive while typing.

## Communication Protocol
Newline-delimited JSON messages, e.g.:
```json
{"type": "login", "username": "alice"}
{"type": "broadcast", "text": "hello everyone"}
{"type": "private", "to": "bob", "text": "hi bob"}
{"type": "disconnect"}
```

## Screenshots
See `screenshots/` for: login window, successful connection, main chat
window, broadcast messaging, private messaging, user joining, and user
leaving.

## Files
```
server.py
client_gui.py
screenshots/
report.pdf
README.md
```
