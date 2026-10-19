import gzip
import re
from datetime import datetime, timezone

import pytest

from gpxsync import Error
from gpxsync.updater import Updater

FILE = b"""<osm version="0.6" timestamp="2026-10-13T10:01:00Z">
  <trace id="7" visible="false"/>
</osm>
"""


def feed(remote):
    """One state.txt per sequence, one minute apart from 10:00."""
    fetched = []

    def fetch(url):
        fetched.append(url)
        if url.endswith("/state.txt"):
            return f"sequenceNumber={remote}\n".encode()
        m = re.search(r"/(\d+)/(\d+)/(\d+)\.state\.txt$", url)
        if m:
            n = int(m.group(3)) + 1000 * int(m.group(2))
            return f"sequenceNumber={n}\ntimestamp=2026-10-13T10\\:{n % 60:02d}\\:00Z\n".encode()
        return gzip.compress(FILE)

    return fetch, fetched


def conn_with(fake_conn, sequence=None, timestamp=None):
    def rows(sql, _):
        if sql.startswith("SELECT sequence") and (sequence is not None or timestamp is not None):
            return [(sequence, timestamp)]
        return []

    return fake_conn(rows)


def test_applies_the_files_after_the_local_sequence(fake_conn):
    fetch, fetched = feed(1002)
    conn = conn_with(fake_conn, sequence=1000)

    applied = Updater(conn, "http://feed/gpx", fetch=fetch).run()

    assert applied == 2
    assert fetched == [
        "http://feed/gpx/state.txt",
        "http://feed/gpx/000/001/001.osm.gz",
        "http://feed/gpx/000/001/002.osm.gz",
    ]
    states = [p[0] for sql, p in conn.queries if sql.startswith("INSERT INTO replication_state")]
    assert states == [1001, 1002]


def test_after_a_dump_starts_from_the_last_file_before_its_timestamp(fake_conn):
    fetch, fetched = feed(10)
    # the dump was taken between the files 7 (10:07) and 8 (10:08)
    conn = conn_with(fake_conn, timestamp=datetime(2026, 10, 13, 10, 7, 30, tzinfo=timezone.utc))

    applied = Updater(conn, "http://feed/gpx/", fetch=fetch).run()

    assert applied == 3
    files = [re.search(r"\d+/\d+/\d+", u).group() for u in fetched if u.endswith(".osm.gz")]
    assert files == ["000/000/008", "000/000/009", "000/000/010"]
    states = [p[0] for sql, p in conn.queries if sql.startswith("INSERT INTO replication_state")]
    assert states == [7, 8, 9, 10], "the sequence found by bisection is stored, so it runs once"


def test_without_state_needs_a_start(fake_conn):
    fetch, _ = feed(5)

    with pytest.raises(Error):
        Updater(fake_conn(), "http://feed/gpx/", fetch=fetch).run()
    assert Updater(fake_conn(), "http://feed/gpx/", fetch=fetch).run(start=3) == 2
