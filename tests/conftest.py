"""A stand-in for a psycopg connection: records the SQL run and the rows
written by each COPY."""

from contextlib import contextmanager

import pytest


class FakeConn:
    def __init__(self, responder=None):
        self.responder = responder or (lambda sql, params: [])
        self.queries = []
        self.copies = {}

    def execute(self, sql, params=None):
        self.queries.append((sql, params))
        return FakeResult(self.responder(sql, params))

    @contextmanager
    def transaction(self):
        yield

    @contextmanager
    def cursor(self):
        yield FakeCursor(self)


class FakeCursor:
    def __init__(self, conn):
        self.conn = conn

    @contextmanager
    def copy(self, sql):
        rows = self.conn.copies.setdefault(sql, [])
        yield FakeCopy(rows)


class FakeCopy:
    def __init__(self, rows):
        self.rows = rows

    def write_row(self, row):
        self.rows.append(tuple(row))


class FakeResult:
    def __init__(self, rows):
        self.rows = rows

    def fetchone(self):
        return self.rows[0] if self.rows else None


@pytest.fixture
def fake_conn():
    return FakeConn
