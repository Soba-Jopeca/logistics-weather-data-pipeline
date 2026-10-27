"""Command-line entry point for published forecast queries."""

import argparse
import json
import sys
from datetime import datetime

from scripts.weather_queries import query_forecasts
from scripts.weather_store import WeatherStoreError


def _parse_instant(value):
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        parsed = datetime.fromisoformat(normalized)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use an ISO-8601 timestamp.") from error
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise argparse.ArgumentTypeError("Timestamp must include a timezone.")
    return parsed


def parse_args(argv=None):
    parser = argparse.ArgumentParser(description="Query a published weather product.")
    parser.add_argument("--location-id", required=True)
    parser.add_argument(
        "--product",
        default="hourly_bundle",
        choices=(
            "temperature_2m",
            "precipitation",
            "wind_speed_10m",
            "hourly_bundle",
        ),
    )
    parser.add_argument(
        "--as-of",
        type=_parse_instant,
        help="Optional ISO-8601 instant; defaults to the current UTC time.",
    )
    return parser.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    try:
        import psycopg2
    except ImportError as error:
        print(f"PostgreSQL driver unavailable: {error.name}", file=sys.stderr)
        return 1

    try:
        rows = query_forecasts(
            args.location_id,
            product_type=args.product,
            as_of=args.as_of,
        )
    except WeatherStoreError as error:
        print(f"Weather query blocked: {error}", file=sys.stderr)
        return 1
    except ValueError as error:
        print(f"Weather query input or artifact is invalid: {error}", file=sys.stderr)
        return 1
    except OSError as error:
        print(f"Weather query I/O failure: {type(error).__name__}", file=sys.stderr)
        return 1
    except ImportError as error:
        print(f"Weather query dependency unavailable: {error.name}", file=sys.stderr)
        return 1
    except psycopg2.Error as error:
        print(f"PostgreSQL query failed: {type(error).__name__}", file=sys.stderr)
        return 1

    if not rows:
        print("Weather query returned no location; check location_id.", file=sys.stderr)
        return 2
    print(json.dumps(rows, default=str, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
