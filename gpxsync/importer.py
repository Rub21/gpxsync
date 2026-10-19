"""Loads a dump, or one replication file, into the database. After a dump,
its timestamp is stored so update knows where to start in the feed."""

import bz2
import gzip
import logging
from pathlib import Path

from gpxsync import schema
from gpxsync.loader import Loader
from gpxsync.reader import read

log = logging.getLogger("gpxsync")


def run(conn, path: str, batch: int = 500) -> int:
    """Returns the number of traces applied."""
    schema.create(conn)
    loader = Loader(conn)
    count = 0
    pending = []
    with open_input(path) as io:
        root, traces = read(io)
        for trace in traces:
            pending.append(trace)
            if len(pending) < batch:
                continue
            count += loader.apply(pending)
            pending.clear()
            log.info("%d traces", count)
    count += loader.apply(pending)
    if "timestamp" in root:
        loader.set_state(None, root["timestamp"])
    log.info("%d traces from %s, dump timestamp %s", count, path, root.get("timestamp"))
    return count


def open_input(path: str):
    suffix = Path(path).suffix
    if suffix == ".gz":
        return gzip.open(path, "rb")
    if suffix == ".bz2":
        return bz2.open(path, "rb")
    return open(path, "rb")
