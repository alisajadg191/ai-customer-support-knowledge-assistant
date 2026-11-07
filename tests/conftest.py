import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from psycopg import sql
from psycopg.conninfo import make_conninfo

from app import create_app
from auth import password_hash
from db import connect
from knowledge import Selection
from seed import ACCOUNTS

PASSWORD = "synthetic-test-password"


class StubModel:
    embedding_model = "deterministic-test"

    def embed(self, texts, *, query=False):
        vectors = []
        for text in texts:
            text = text.lower()
            if "refund" in text:
                vectors.append([1, 0, 0])
            elif "delivery" in text:
                vectors.append([0, 1, 0])
            else:
                vectors.append([0, 0, 1])
        return vectors

    def chat(self, instruction, data, schema):
        if schema is Selection:
            return schema(source_ids=[1, 1, 999])
        assert data["sources"][0]["title"] == "Refunds"
        return schema(reply="Please return your unused item within 30 days.")


@pytest.fixture
def database_url():
    base = os.getenv("TEST_DATABASE_URL")
    if not base:
        pytest.fail("Set TEST_DATABASE_URL to a PostgreSQL database with pgvector")
    schema = f"test_{uuid4().hex}"
    identifier = sql.Identifier(schema)
    with connect(base) as connection:
        connection.execute("CREATE EXTENSION IF NOT EXISTS vector WITH SCHEMA public")
        connection.execute(sql.SQL("CREATE SCHEMA {}").format(identifier))
    try:
        yield make_conninfo(base, options=f"-c search_path={schema},public")
    finally:
        with connect(base) as connection:
            connection.execute(sql.SQL("DROP SCHEMA {} CASCADE").format(identifier))


@pytest.fixture
def demo(database_url):
    model = StubModel()
    with TestClient(create_app(database_url, model)) as client:
        with connect(database_url) as connection:
            for email, role in ACCOUNTS:
                connection.execute("INSERT INTO accounts (email, password_hash, role) VALUES (%s, %s, %s)",
                                   (email, password_hash(PASSWORD), role))
        yield client, model


def login(client, identity):
    result = client.post("/auth/login", json={"email": f"{identity}@example.test", "password": PASSWORD})
    assert result.status_code == 200, result.text
    return {"Authorization": f"Bearer {result.json()['token']}"}
