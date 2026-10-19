"""Writes traces into PostGIS. A batch is one transaction: the rows of every
trace in it are deleted, then the traces with content are written again with
COPY. Applying a batch twice gives the same result."""

import struct
import sys
from array import array
from dataclasses import dataclass
from datetime import datetime

from gpxsync.reader import Trace

SRID = 4326
WKB_POINT_ZM = 0xE0000001
WKB_LINESTRING_ZM = 0xE0000002
TRACES_COPY_SQL = (
    'COPY traces (id, visibility, uid, "user", "timestamp", name, description, points, lat, lon) FROM STDIN'
)
SET_STATE_SQL = (
    'INSERT INTO replication_state (id, sequence, "timestamp") VALUES (1, %s, %s) '
    'ON CONFLICT (id) DO UPDATE SET sequence = EXCLUDED.sequence, "timestamp" = EXCLUDED."timestamp"'
)


@dataclass
class Position:
    """Where the database is in the feed: the last sequence applied, or only
    the timestamp of the dump when no feed file was applied yet."""

    sequence: int | None
    timestamp: datetime | None


class Loader:
    def __init__(self, conn):
        self.conn = conn

    def apply(self, traces: list[Trace]) -> int:
        if not traces:
            return 0
        with self.conn.transaction():
            self.conn.execute("DELETE FROM traces WHERE id = ANY(%s)", ([t.id for t in traces],))
            with_content = [t for t in traces if t.content]
            self.copy(
                TRACES_COPY_SQL,
                [
                    (t.id, t.visibility, t.uid, t.user, t.timestamp, t.name, t.description, t.points, t.lat, t.lon)
                    for t in with_content
                ],
            )
            self.copy("COPY trace_tags (gpx_id, tag) FROM STDIN", [(t.id, tag) for t in with_content for tag in t.tags])
            self.copy(
                "COPY trace_segments (gpx_id, trackid, geom) FROM STDIN",
                [(t.id, i, ewkb_hex(seg)) for t in with_content for i, seg in enumerate(t.segments) if len(seg)],
            )
        return len(traces)

    def state(self) -> Position | None:
        row = self.conn.execute('SELECT sequence, "timestamp" FROM replication_state WHERE id = 1').fetchone()
        return Position(row[0], row[1]) if row else None

    def set_state(self, sequence: int | None, timestamp: str | datetime | None) -> None:
        self.conn.execute(SET_STATE_SQL, (sequence, timestamp))

    def copy(self, sql: str, rows: list[tuple]) -> None:
        with self.conn.cursor() as cursor, cursor.copy(sql) as copy:
            for row in rows:
                copy.write_row(row)


def ewkb_hex(segment: array) -> str:
    """EWKB, little endian, with SRID: binary keeps -inf in M as it is. The
    segment is the flat array of the reader, 4 doubles per point."""
    if sys.byteorder != "little":
        segment = array("d", segment)
        segment.byteswap()
    count = len(segment) // 4
    if count == 1:
        return (struct.pack("<BII", 1, WKB_POINT_ZM, SRID) + segment.tobytes()).hex()
    return (struct.pack("<BIII", 1, WKB_LINESTRING_ZM, SRID, count) + segment.tobytes()).hex()
