"""The tables: one row per trace, its tags, and one geometry per <trkseg>
with the altitude in Z and the time in M. geom2d is for the tile server,
ST_AsMVTGeom cannot clip ZM lines."""

SQL = """
SET LOCAL client_min_messages = warning;
CREATE EXTENSION IF NOT EXISTS postgis;

CREATE TABLE IF NOT EXISTS traces (
  id bigint PRIMARY KEY,
  visibility text NOT NULL,
  uid bigint,
  "user" text,
  "timestamp" timestamptz,
  name text,
  description text,
  points integer,
  lat double precision,
  lon double precision
);

CREATE TABLE IF NOT EXISTS trace_tags (
  gpx_id bigint NOT NULL REFERENCES traces(id) ON DELETE CASCADE,
  tag text NOT NULL
);
CREATE INDEX IF NOT EXISTS trace_tags_gpx_id_idx ON trace_tags (gpx_id);

CREATE TABLE IF NOT EXISTS trace_segments (
  gpx_id bigint NOT NULL REFERENCES traces(id) ON DELETE CASCADE,
  trackid integer NOT NULL,
  geom geometry(GeometryZM, 4326) NOT NULL,
  geom2d geometry(Geometry, 4326) GENERATED ALWAYS AS (ST_Force2D(geom)) STORED,
  PRIMARY KEY (gpx_id, trackid)
);
CREATE INDEX IF NOT EXISTS trace_segments_geom_idx ON trace_segments USING gist (geom);
CREATE INDEX IF NOT EXISTS trace_segments_geom2d_idx ON trace_segments USING gist (geom2d);

-- Where the database is in the feed. sequence is null right after a dump:
-- only its timestamp is known, update finds the sequence.
CREATE TABLE IF NOT EXISTS replication_state (
  id integer PRIMARY KEY DEFAULT 1 CHECK (id = 1),
  sequence bigint,
  "timestamp" timestamptz
);
ALTER TABLE replication_state ALTER COLUMN sequence DROP NOT NULL;
"""


def create(conn) -> None:
    with conn.transaction():
        conn.execute(SQL)
