import hashlib
import hmac
import secrets
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel, SecretStr, StringConstraints

from db import connect

bearer = HTTPBearer(auto_error=False)


class Login(BaseModel):
    email: Annotated[str, StringConstraints(strip_whitespace=True, min_length=3, max_length=254)]
    password: SecretStr


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt=None):
    salt = salt if salt is not None else secrets.token_hex(16)
    key = hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=2**15, r=8, p=1, maxmem=64*1024**2)
    return f"{salt}:{key.hex()}"


def auth_routes(dsn):
    router = APIRouter(prefix="/auth")
    dummy_hash = password_hash(secrets.token_hex(16))

    @router.post("/login")
    def login(payload: Login):
        password = payload.password.get_secret_value()
        if not 1 <= len(password) <= 256:
            raise HTTPException(401, "Invalid credentials")
        with connect(dsn) as connection:
            account = connection.execute(
                "SELECT * FROM accounts WHERE email = %s", (payload.email.lower(),)
            ).fetchone()
            stored = account["password_hash"] if account else dummy_hash
            valid = hmac.compare_digest(stored, password_hash(password, stored.split(":")[0]))
            if not valid or account is None:
                raise HTTPException(401, "Invalid credentials")
            token = secrets.token_urlsafe(32)
            connection.execute("DELETE FROM sessions WHERE expires_at <= now()")
            connection.execute("""
                INSERT INTO sessions VALUES (%s, %s, now() + interval '8 hours')
            """, (digest(token), account["id"]))
        return {"token": token, "role": account["role"]}

    def current_user(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if credentials is None:
            raise HTTPException(401, "Sign in required", headers={"WWW-Authenticate": "Bearer"})
        with connect(dsn) as connection:
            account = connection.execute("""
                SELECT accounts.id, email, role FROM accounts JOIN sessions
                ON sessions.account_id = accounts.id
                WHERE token_hash = %s AND expires_at > now()
            """, (digest(credentials.credentials),)).fetchone()
        if account is None:
            raise HTTPException(401, "Session expired or invalid", headers={"WWW-Authenticate": "Bearer"})
        return account

    @router.post("/logout", status_code=204)
    def logout(credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
        if credentials is not None:
            with connect(dsn) as connection:
                connection.execute("DELETE FROM sessions WHERE token_hash = %s", (digest(credentials.credentials),))
        return Response(status_code=204)

    def require_staff(account=Depends(current_user)):
        if account["role"] != "staff":
            raise HTTPException(403, "Staff access required")
        return account

    def require_customer(account=Depends(current_user)):
        if account["role"] != "customer":
            raise HTTPException(403, "Customer access required")
        return account

    return router, current_user, require_staff, require_customer
