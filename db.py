from pathlib import Path

import psycopg
from psycopg.rows import dict_row


def connect(dsn):
    return psycopg.connect(dsn, row_factory=dict_row, connect_timeout=5)


def initialize(dsn):
    with connect(dsn) as connection:
        connection.execute(Path(__file__).with_name("schema.sql").read_text())
