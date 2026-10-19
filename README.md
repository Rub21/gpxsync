# gpxsync

Keeps a PostGIS copy of the OpenStreetMap GPS traces up to date from the
full dump and the minute replication feed written by
[osmrep](https://github.com/Rub21/osmrep). It is the consumer side for a
GPS tiles server.

```
pip install .
gpxsync import gpx-planet-latest.osm.bz2             # load a dump, or one replication file
gpxsync update --url https://.../replication/gpx/    # apply the new files of the feed
```

`--database URL` or `$GPXSYNC_DATABASE` is the PostGIS database. The feed
can also come from `$GPXSYNC_FEED_URL`.

## How it works

`import` reads the file as a stream (`lxml` iterparse) and writes the traces
with `COPY`, 100 per transaction. After a dump, the dump timestamp is stored.

`update` applies every feed file newer than the stored sequence, one
transaction per file, storing the sequence after each one. Right after a
dump only the timestamp is known: `update` finds the last feed file written
before it, like pyosmium does with the planet, and continues from there.
Without any state, `--start SEQUENCE` says where to begin.

Each trace in a file replaces its rows; a `visible="false"` trace removes
them. Applying a file twice gives the same result.

The full dump is loaded once. If reading it in Python turns out too slow for
the production size, `import` alone can be rewritten in a compiled language;
`update` stays as it is.

## Tables

Created when missing:

```
traces(id, visibility, uid, "user", "timestamp", name, description, points, lat, lon)
trace_tags(gpx_id, tag)
trace_segments(gpx_id, trackid, geom geometry(GeometryZM, 4326), geom2d)   -- one per <trkseg>
replication_state(sequence, "timestamp")
```

`geom` has the altitude in Z and the time in M. `geom2d` is a generated 2D
copy for tile servers, `ST_AsMVTGeom` cannot clip ZM lines.

## Development

```
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
```
