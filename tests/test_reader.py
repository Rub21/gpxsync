import io

from gpxsync.reader import NO_TIME, read

XML = b"""<?xml version="1.0" encoding="UTF-8"?>
<osm version="0.6" generator="osmrep" timestamp="2026-10-13T10:00:00Z">
  <trace id="7" visible="true" visibility="identifiable" timestamp="2026-10-13T09:00:00Z"
         uid="3" user="ruben" lat="-12.05" lon="-77.04" points="3">
    <name>ruta.gpx</name>
    <description>Lima &amp; Callao</description>
    <tag v="bike"/>
    <trk>
      <trkseg>
        <trkpt lat="-12.05" lon="-77.04"><ele>10.5</ele><time>2026-10-13T08:00:00Z</time></trkpt>
        <trkpt lat="-12.0501" lon="-77.0401"><time>2026-10-13T08:00:05Z</time></trkpt>
      </trkseg>
      <trkseg>
        <trkpt lat="-12.06" lon="-77.05"/>
      </trkseg>
    </trk>
  </trace>
  <trace id="9" visible="false"/>
</osm>
"""


def test_reads_the_root_and_the_traces():
    root, traces = read(io.BytesIO(XML))
    traces = list(traces)

    assert root["timestamp"] == "2026-10-13T10:00:00Z"
    t = traces[0]
    assert t.id == 7
    assert t.content
    assert t.user == "ruben"
    assert t.description == "Lima & Callao"
    assert t.tags == ["bike"]
    assert len(t.segments) == 2
    assert t.segments[0][0] == [-77.04, -12.05, 10.5, 1791878400.0]
    assert t.segments[1][0][3] == NO_TIME
    assert not traces[1].visible
    assert not traces[1].content
