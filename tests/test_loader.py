from datetime import datetime, timezone

from gpxsync.loader import Loader
from gpxsync.reader import Trace


def trace(id, **attrs):
    values = dict(
        id=id,
        visible=True,
        visibility="identifiable",
        uid=3,
        user="ruben",
        timestamp="2026-10-13T09:00:00Z",
        name="a\tb",
        description=None,
        points=2,
        lat=-12.05,
        lon=-77.04,
        tags=["bike"],
        segments=[[[-77.04, -12.05, 10.5, 1.0], [-77.05, -12.06, 0.0, float("-inf")]], [[-77.06, -12.07, 0.0, 2.0]]],
    )
    values.update(attrs)
    return Trace(**values)


def test_apply_deletes_then_copies_the_traces_with_content(fake_conn):
    conn = fake_conn()
    deleted = trace(9, visible=False, lat=None, segments=[], tags=[])

    count = Loader(conn).apply([trace(7), deleted])

    assert count == 2
    delete = next(q for q in conn.queries if q[0].startswith("DELETE FROM traces"))
    assert delete[1] == ([7, 9],)
    traces_copy = next(k for k in conn.copies if k.startswith("COPY traces"))
    assert conn.copies[traces_copy] == [
        (7, "identifiable", 3, "ruben", "2026-10-13T09:00:00Z", "a\tb", None, 2, -12.05, -77.04)
    ]
    assert conn.copies["COPY trace_tags (gpx_id, tag) FROM STDIN"] == [(7, "bike")]
    segments = conn.copies["COPY trace_segments (gpx_id, trackid, geom) FROM STDIN"]
    assert len(segments) == 2
    # 01 little endian, type 0xE0000002 = linestring ZM with SRID, SRID 4326 = 0x10E6
    assert segments[0][:2] == (7, 0) and segments[0][2].startswith("01020000e0e6100000")
    assert segments[1][:2] == (7, 1) and segments[1][2].startswith("01010000e0e6100000")


def test_state_after_a_dump_has_only_the_timestamp(fake_conn):
    when = datetime(2026, 10, 19, 14, 22, 10, tzinfo=timezone.utc)
    conn = fake_conn(lambda sql, _: [(None, when)] if sql.startswith("SELECT sequence") else [])

    state = Loader(conn).state()

    assert state.sequence is None
    assert state.timestamp == when
