# Assignment 7 – Secure Network Application Development Using TCP

**Name:** Tanvi Chaudhari
**Roll No:** 5130108

## Overview
This project extends the Assignment 6 GUI-based multi-client TCP chat
application with practical application-security features: authentication,
SHA-256 password hashing, duplicate-login prevention, input validation,
failed-login protection, and session management with secure logging.

## Files
| File | Purpose |
|---|---|
| `server.py` | Multi-threaded TCP server with all security logic |
| `client_gui.py` | Tkinter GUI client (login screen + chat screen) |
| `generate_users.py` | One-time helper that writes `users.csv` with SHA-256 hashed passwords |
| `users.csv` | User database — **hashes only**, never plaintext |
| `security_log.txt` | Sample security event log generated during testing |
| `report.pdf` | Full assignment report |
| `handwritten_reflection.pdf` | Scanned handwritten reflection answers |
| `screenshots/` | Evidence screenshots (login, blocked login, chat, Wireshark) |

## How to Run

### 1. Set up the network (Mininet)
```bash
sudo mn --topo single,5
mininet> nodes
mininet> net
mininet> pingall
```

### 2. Create user accounts
```bash
python3 generate_users.py
```
Edit the `ACCOUNTS` dictionary in `generate_users.py` to add more users.
Only SHA-256 hashes are ever written to `users.csv`.

### 3. Start the server
```bash
python3 server.py
```
The server listens on TCP port **5000** on all interfaces.

### 4. Start one or more clients
```bash
python3 client_gui.py
```
Update `HOST` in `client_gui.py` if the client runs on a different Mininet
host than the server.

## Security Features Implemented
1. **Authentication** – username/password required before any chat action.
2. **Secure password storage** – `hashlib.sha256()`; plaintext is never
   written to disk or logged.
3. **Duplicate login prevention** – server tracks active usernames in
   memory and rejects a second simultaneous login.
4. **Input validation** – username format (regex), non-empty password,
   1024-byte message cap, and a whitelist of supported commands.
5. **Failed login protection** – 5 consecutive failed attempts locks the
   account for 60 seconds.
6. **Session management** – `LOGOUT` command, 120-second inactivity
   timeout, and a secure event log (`security_log.txt`) that never
   contains passwords.

## Testing
Both a scripted protocol test and manual GUI testing were used to verify
every task (see `report.pdf` → *Testing* section for full transcripts and
screenshots).

## Wireshark Verification
Captures were taken with filter `tcp.port == 5000` covering: successful
login, failed login, authenticated chat traffic, and logout. See
`report.pdf` → *Wireshark Verification* and `screenshots/`.
