"""Follows the feed: applies every file after the stored sequence, one
transaction per file, storing the sequence after each one. Right after a
dump only its timestamp is known; the sequence is then the last feed file
written before that time, like pyosmium does with the planet."""

import gzip
import io
import logging
from collections.abc import Callable
from datetime import datetime
from urllib.request import Request, urlopen

from gpxsync import Error, __version__, schema
from gpxsync.loader import Loader, Position
from gpxsync.reader import read
from gpxsync.state import State

log = logging.getLogger("gpxsync")


def http_get(url: str) -> bytes:
    # With its own User-Agent, as the OSM servers ask; the default one of
    # urllib is refused by some proxies.
    with urlopen(Request(url, headers={"User-Agent": f"gpxsync/{__version__}"})) as response:
        return response.read()


class Updater:
    def __init__(self, conn, url: str, max_files: int = 1000, fetch: Callable[[str], bytes] = http_get):
        self.conn = conn
        self.url = url if url.endswith("/") else url + "/"
        self.max_files = max_files
        self.fetch = fetch

    def run(self, start: int | None = None) -> int:
        """Returns the number of files applied. start is the sequence to begin
        after when the database has no state at all."""
        schema.create(self.conn)
        loader = Loader(self.conn)
        remote = State.parse(self.text(self.url + "state.txt")).sequence
        state = loader.state()
        local = self.local_sequence(state, remote, start)
        if state is not None and state.sequence is None:
            loader.set_state(local, state.timestamp)  # the bisection runs once
        log.info("local sequence %d, feed sequence %d", local, remote)

        applied = 0
        for sequence in range(local + 1, remote + 1)[: self.max_files]:
            self.apply_file(loader, sequence)
            applied += 1
        log.info("%d files applied, sequence %d", applied, local + applied)
        return applied

    def local_sequence(self, state: Position | None, remote: int, start: int | None) -> int:
        if state and state.sequence is not None:
            return state.sequence
        if state and state.timestamp is not None:
            return self.sequence_before(state.timestamp, remote)
        if start is not None:
            return start
        raise Error("no replication state in the database, import a dump first or pass --start SEQUENCE")

    def sequence_before(self, time: datetime, remote: int) -> int:
        """The last sequence whose state.txt is not after the time, by bisection."""
        low, high = 0, remote
        while low < high:
            mid = (low + high + 1) // 2
            if State.parse(self.text(f"{self.url}{path(mid)}.state.txt")).timestamp <= time:
                low = mid
            else:
                high = mid - 1
        log.info("dump timestamp %s is after feed sequence %d", time.isoformat(), low)
        return low

    def apply_file(self, loader: Loader, sequence: int) -> None:
        body = self.fetch(f"{self.url}{path(sequence)}.osm.gz")
        with gzip.open(io.BytesIO(body), "rb") as file:
            root, traces = read(file)
            count = loader.apply(list(traces))
        loader.set_state(sequence, root.get("timestamp"))
        log.info("%s.osm.gz: %d traces", path(sequence), count)

    def text(self, url: str) -> str:
        return self.fetch(url).decode()


def path(sequence: int) -> str:
    return f"{sequence // 1_000_000:03d}/{(sequence // 1000) % 1000:03d}/{sequence % 1000:03d}"
