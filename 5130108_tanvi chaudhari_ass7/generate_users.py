"""
generate_users.py - One-time helper to create users.csv with SHA-256 hashed
passwords. Run this once before starting server.py.

Usage:
    python3 generate_users.py

Edit the ACCOUNTS dictionary below to add/remove users, then run the script.
It NEVER writes plaintext passwords to disk - only SHA-256 hashes.
"""

import csv
import hashlib

# Define plaintext passwords here only for generation purposes.
# This file is not required at runtime - only users.csv (with hashes) is used.
ACCOUNTS = {
    "tanvi": "Tanvi@123",
    "alice": "Alice#456",
    "bob": "Bob$789",
}

OUTPUT_FILE = "users.csv"


def main():
    with open(OUTPUT_FILE, "w", newline="") as f:
        writer = csv.writer(f)
        for username, password in ACCOUNTS.items():
            hashed = hashlib.sha256(password.encode("utf-8")).hexdigest()
            writer.writerow([username, hashed])
    print(f"[OK] Wrote {len(ACCOUNTS)} user(s) with hashed passwords to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
