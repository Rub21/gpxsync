"""gpxsync import FILE | gpxsync update [--start N]"""

import argparse
import logging
import os
import sys

import psycopg

from gpxsync import Error, __version__, importer
from gpxsync.updater import Updater


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="gpxsync", description="Loads the GPS traces dump and replication feed into PostGIS"
    )
    parser.add_argument(
        "-d",
        "--database",
        default=os.environ.get("GPXSYNC_DATABASE"),
        help="PostGIS database URL (default: $GPXSYNC_DATABASE)",
    )
    parser.add_argument("-q", "--quiet", action="store_true", help="no log output")
    parser.add_argument("-v", "--version", action="version", version=__version__)
    commands = parser.add_subparsers(dest="command", required=True)
    cmd = commands.add_parser("import", help="load a dump or a replication file")
    cmd.add_argument("file")
    cmd = commands.add_parser("update", help="apply the new files of the feed")
    cmd.add_argument(
        "-u",
        "--url",
        default=os.environ.get("GPXSYNC_FEED_URL"),
        help="the feed, the directory with state.txt (default: $GPXSYNC_FEED_URL)",
    )
    cmd.add_argument("-s", "--start", type=int, help="sequence to begin after when the database has no state")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.WARNING if args.quiet else logging.INFO, format="%(asctime)s %(message)s")
    try:
        if not args.database:
            raise Error("database is not set (--database or GPXSYNC_DATABASE)")
        if args.command == "update" and not args.url:
            raise Error("feed url is not set (--url or GPXSYNC_FEED_URL)")
        with psycopg.connect(args.database) as conn:
            if args.command == "import":
                importer.run(conn, args.file)
            else:
                Updater(conn, args.url).run(start=args.start)
        return 0
    except (Error, psycopg.Error) as e:
        print(f"gpxsync: {e}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
