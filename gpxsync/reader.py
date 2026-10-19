"""Streams the <trace> elements of a dump or a replication file."""

from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import IO

from lxml import etree

from gpxsync.state import parse_time

NO_TIME = float("-inf")


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
    # One list per <trkseg>, each point [lon, lat, ele, time]; ele 0 and
    # time -inf when the point has none, as gpx_tracks stores them.
    segments: list[list[list[float]]] = field(default_factory=list)

    @property
    def content(self) -> bool:
        """True when the file carries the points, not only a header."""
        return self.visible and self.lat is not None


def read(io: IO[bytes]) -> tuple[dict[str, str], Iterator[Trace]]:
    """The attributes of <osm> and an iterator over its traces. Each trace is
    freed after it is yielded, so a dump of any size reads in little memory."""
    parser = etree.iterparse(io, events=("start", "end"))
    root: dict[str, str] = {}

    def traces() -> Iterator[Trace]:
        for event, elem in parser:
            if event == "start" and elem.tag == "osm":
                root.update(elem.attrib)
            elif event == "end" and elem.tag == "trace":
                yield trace_of(elem)
                elem.clear()
                while elem.getprevious() is not None:
                    del elem.getparent()[0]

    # Read up to the root so its attributes are known before the first trace.
    event, elem = next(parser)
    if elem.tag == "osm":
        root.update(elem.attrib)
    return root, traces()


def trace_of(elem: etree._Element) -> Trace:
    a = elem.attrib
    trace = Trace(
        id=int(a["id"]),
        visible=a.get("visible") == "true",
        visibility=a.get("visibility"),
        uid=int(a["uid"]) if "uid" in a else None,
        user=a.get("user"),
        timestamp=a.get("timestamp"),
        points=int(a["points"]) if "points" in a else None,
        lat=float(a["lat"]) if "lat" in a else None,
        lon=float(a["lon"]) if "lon" in a else None,
    )
    for child in elem:
        if child.tag == "name":
            trace.name = child.text
        elif child.tag == "description":
            trace.description = child.text
        elif child.tag == "tag":
            trace.tags.append(child.get("v"))
        elif child.tag == "trk":
            trace.segments = [[point_of(p) for p in seg.iter("trkpt")] for seg in child.iter("trkseg")]
    return trace


def point_of(elem: etree._Element) -> list[float]:
    ele = elem.find("ele")
    time = elem.find("time")
    return [
        float(elem.get("lon")),
        float(elem.get("lat")),
        float(ele.text) if ele is not None else 0.0,
        parse_time(time.text).timestamp() if time is not None else NO_TIME,
    ]
