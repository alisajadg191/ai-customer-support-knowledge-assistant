import os
from getpass import getpass

from auth import password_hash
from db import connect, initialize

ACCOUNTS = (
    ("customer@example.test", "customer"),
    ("other@example.test", "customer"),
    ("staff@example.test", "staff"),
)


def main():
    dsn = os.environ["DATABASE_URL"]
    initialize(dsn)
    with connect(dsn) as connection:
        existing = {row["email"] for row in connection.execute("SELECT email FROM accounts")}

    new_accounts = []
    passwords = set()
    for email, role in ACCOUNTS:
        if email in existing:
            continue
        password = getpass(f"Choose a unique demo password for {email}: ")
        if not 12 <= len(password) <= 256 or password in passwords:
            raise SystemExit("Use a different password of 12–256 characters for each account.")
        passwords.add(password)
        new_accounts.append((email, password_hash(password), role))

    with connect(dsn) as connection:
        for account in new_accounts:
            connection.execute("""
                INSERT INTO accounts (email, password_hash, role) VALUES (%s, %s, %s)
                ON CONFLICT (email) DO NOTHING
            """, account)
    print("Demo accounts available:", ", ".join(email for email, _ in ACCOUNTS))


if __name__ == "__main__":
    main()
