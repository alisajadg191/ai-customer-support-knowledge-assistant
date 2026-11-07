import os

from auth import password_hash
from db import connect, initialize

ACCOUNTS = (
    ("customer@example.test", "customer"),
    ("other@example.test", "customer"),
    ("staff@example.test", "staff"),
)


def main():
    password = os.environ.get("DEMO_PASSWORD", "")
    if not 12 <= len(password) <= 256:
        raise SystemExit("Set DEMO_PASSWORD to a unique demo password of 12–256 characters.")
    dsn = os.environ["DATABASE_URL"]
    initialize(dsn)
    with connect(dsn) as connection:
        for email, role in ACCOUNTS:
            connection.execute("""
                INSERT INTO accounts (email, password_hash, role) VALUES (%s, %s, %s)
                ON CONFLICT (email) DO NOTHING
            """, (email, password_hash(password), role))
    print("Demo accounts available:", ", ".join(email for email, _ in ACCOUNTS))


if __name__ == "__main__":
    main()
