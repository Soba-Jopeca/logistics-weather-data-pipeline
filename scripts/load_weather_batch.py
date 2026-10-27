"""Explicit PostgreSQL migration and verified batch-load entry point."""

import argparse
import json
import sys

from scripts.weather_store import (
    SCHEMA_VERSION,
    WeatherStoreError,
    apply_weather_schema,
    build_load_package,
    connect_weather_database,
    persist_load_package,
)


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        description="Load an already verified Raw batch into PostgreSQL."
    )
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--batch-id", help="UUID of a completed, verified batch.")
    mode.add_argument(
        "--migrate",
        action="store_true",
        help="Apply the additive schema migration explicitly.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        import psycopg2
    except ImportError as error:
        print(f"PostgreSQL driver unavailable: {error.name}", file=sys.stderr)
        return 1

    connection = None
    try:
        if args.migrate:
            connection = connect_weather_database()
            with connection:
                apply_weather_schema(connection)
            print(json.dumps({"migrations": [SCHEMA_VERSION, "002_weather_raw_staging"], "applied": True}))
            return 0

        package = build_load_package(args.batch_id)
        result = persist_load_package(
            package,
            connect=connect_weather_database,
        )
        print(json.dumps(result, sort_keys=True))
        return 0
    except WeatherStoreError as error:
        print(f"Weather load blocked: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Weather load input or artifact is invalid: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Weather load I/O failure: {type(error).__name__}", file=sys.stderr)
        return 1
    except ImportError as error:
        print(f"Weather load dependency unavailable: {error.name}", file=sys.stderr)
        return 1
    except psycopg2.Error as error:
        print(f"PostgreSQL operation failed: {type(error).__name__}", file=sys.stderr)
        return 1
    finally:
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
