"""Streams the <trace> elements of a dump or a replication file with expat,
an event parser: no tree is built, so a dump of any size reads in the
memory of one trace."""

from array import array
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import IO
from xml.parsers import expat

from gpxsync.state import parse_time

NO_TIME = float("-inf")
CHUNK = 1 << 20


@dataclass
class Trace:
    id: int
    visible: bool
    visibility: str | None = None
    uid: int | None = None
    user: str | None = None
    timestamp: str | None = None
    name: str | None = None
    description: str | None = None
    points: int | None = None
    lat: float | None = None
    lon: float | None = None
    tags: list[str] = field(default_factory=list)
    # One array per <trkseg>: lon, lat, ele, time for each point, flat. ele is
    # 0 and time -inf when the point has none, as gpx_tracks stores them.
    segments: list[array] = field(default_factory=list)

    @property
    def content(self) -> bool:
        """True when the file carries the points, not only a header."""
        return self.visible and self.lat is not None


def read(io: IO[bytes]) -> tuple[dict[str, str], Iterator[Trace]]:
    """The attributes of <osm> and an iterator over its traces."""
    handler = Handler()
    parser = expat.ParserCreate()
    parser.StartElementHandler = handler.start
    parser.EndElementHandler = handler.end
    parser.CharacterDataHandler = handler.characters
    parser.buffer_text = True

    def traces() -> Iterator[Trace]:
        while chunk := io.read(CHUNK):
            parser.Parse(chunk, False)
            yield from handler.done
            handler.done.clear()
        parser.Parse(b"", True)
        yield from handler.done
        handler.done.clear()

    # The root comes before the first trace, so one chunk is enough for its
    # attributes; its traces are kept for the iterator.
    parser.Parse(io.read(CHUNK), False)
    return handler.root, traces()


class Handler:
    def __init__(self):
        self.root: dict[str, str] = {}
        self.done: list[Trace] = []
        self.trace: Trace | None = None
        self.segment: array | None = None
        self.point: list[float] | None = None
        self.text: list[str] | None = None

    def start(self, name: str, attrs: dict[str, str]) -> None:
        if name == "trkpt":
            self.point = [float(attrs["lon"]), float(attrs["lat"]), 0.0, NO_TIME]
        elif name in ("ele", "time", "name", "description"):
            self.text = []
        elif name == "trkseg":
            self.segment = array("d")
        elif name == "tag":
            self.trace.tags.append(attrs["v"])
        elif name == "trace":
            self.trace = Trace(
                id=int(attrs["id"]),
                visible=attrs.get("visible") == "true",
                visibility=attrs.get("visibility"),
                uid=int(attrs["uid"]) if "uid" in attrs else None,
                user=attrs.get("user"),
                timestamp=attrs.get("timestamp"),
                points=int(attrs["points"]) if "points" in attrs else None,
                lat=float(attrs["lat"]) if "lat" in attrs else None,
                lon=float(attrs["lon"]) if "lon" in attrs else None,
            )
        elif name == "osm":
            self.root.update(attrs)

    def characters(self, data: str) -> None:
        if self.text is not None:
            self.text.append(data)

    def end(self, name: str) -> None:
        if name == "trkpt":
            self.segment.extend(self.point)
        elif name == "ele":
            self.point[2] = float(self.take_text())
        elif name == "time":
            self.point[3] = parse_time(self.take_text()).timestamp()
        elif name == "trkseg":
            self.trace.segments.append(self.segment)
        elif name == "name":
            self.trace.name = self.take_text()
        elif name == "description":
            self.trace.description = self.take_text()
        elif name == "trace":
            self.done.append(self.trace)

    def take_text(self) -> str:
        text = "".join(self.text)
        self.text = None
        return text
