"""Read-only, as-of queries for published forecast products."""

from datetime import datetime, timezone
from pathlib import Path

from scripts.weather_store import PROJECT_ROOT, WeatherStoreError, connect_weather_database


PRODUCT_TYPES = {
    "temperature_2m",
    "precipitation",
    "wind_speed_10m",
    "hourly_bundle",
}
FORECAST_QUERY_PATH = PROJECT_ROOT / "sql" / "queries" / "forecast_by_location.sql"


def _validate_as_of(as_of):
    if as_of is None:
        return datetime.now(timezone.utc)
    if not isinstance(as_of, datetime) or as_of.tzinfo is None:
        raise WeatherStoreError("as_of must be a timezone-aware datetime.")
    if as_of.utcoffset() is None:
        raise WeatherStoreError("as_of must be a timezone-aware datetime.")
    return as_of.astimezone(timezone.utc)


def query_forecasts(
    location_id,
    *,
    product_type="hourly_bundle",
    as_of=None,
    connect=connect_weather_database,
):
    """Return one complete published version, or explicit unavailability."""
    if (
        not isinstance(location_id, str)
        or not location_id.strip()
        or location_id != location_id.strip()
    ):
        raise WeatherStoreError("location_id is required.")
    if not isinstance(product_type, str) or product_type not in PRODUCT_TYPES:
        raise WeatherStoreError("Unsupported product_type.")

    as_of_utc = _validate_as_of(as_of)
    query = Path(FORECAST_QUERY_PATH).read_text(encoding="utf-8")
    connection = connect()
    try:
        from psycopg2.extras import RealDictCursor

        with connection.cursor(cursor_factory=RealDictCursor) as cursor:
            cursor.execute(query, (location_id, as_of_utc, product_type))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        connection.close()
