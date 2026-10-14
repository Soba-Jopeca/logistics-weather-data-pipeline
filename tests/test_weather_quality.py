from datetime import datetime, timezone

import pytest

import scripts.extract_weather as extractor


def test_five_locations_have_expected_identity(locations):
    assert {item["location_id"] for item in locations} == {
        "br_sp_campinas",
        "br_sp_sao_paulo",
        "br_sp_sorocaba",
        "br_sp_jundiai",
        "br_sp_ribeirao_preto",
    }
    assert len(locations) == 5
    assert all(
        item["timezone"] == "America/Sao_Paulo"
        for item in locations
    )


def test_valid_payload_produces_32_linked_records(
    locations, payload_factory, cycle_date
):
    location = locations[0]
    payload = payload_factory(location)
    window = extractor.build_cycle_window(
        cycle_date, location["timezone"]
    )

    records, validation = extractor.process_forecast(
        payload,
        window,
        datetime(2026, 10, 13, 17, tzinfo=timezone.utc),
        "run-teste",
        location["location_id"],
    )

    assert len(records) == 32
    assert validation["coverage"]["coverage_complete"] is True
    assert all(item["run_id"] == "run-teste" for item in records)
    assert all(
        item["location_id"] == location["location_id"]
        for item in records
    )
    assert len({
        (item["run_id"], item["forecast_time_utc"])
        for item in records
    }) == 32


def test_null_is_preserved_and_not_replaced_by_zero(
    locations, payload_factory
):
    payload = payload_factory(locations[0])
    payload["hourly"]["temperature_2m"][1] = None

    hourly = extractor.validate_payload_structure(payload)
    counts = extractor.validate_weather_values(hourly)
    times = extractor.parse_forecast_times(payload)
    records = extractor.normalize_forecasts(
        hourly, times, "run-teste", locations[0]["location_id"]
    )

    assert counts["temperature_2m"] == 1
    assert records[1]["temperature_2m_c"] is None
    assert payload["hourly"]["temperature_2m"][1] is None
    assert records[1]["precipitation_mm"] == 0.0


@pytest.mark.parametrize(
    "field",
    ["time", "temperature_2m", "precipitation", "wind_speed_10m"],
)
def test_missing_series_is_rejected(
    locations, payload_factory, field
):
    payload = payload_factory(locations[0])
    del payload["hourly"][field]

    with pytest.raises(ValueError):
        extractor.validate_payload_structure(payload)


def test_different_series_lengths_are_rejected(
    locations, payload_factory
):
    payload = payload_factory(locations[0])
    payload["hourly"]["precipitation"].pop()

    with pytest.raises(ValueError):
        extractor.validate_payload_structure(payload)


@pytest.mark.parametrize(
    "field, wrong_unit",
    [
        ("time", "iso8601"),
        ("temperature_2m", "°F"),
        ("precipitation", "inch"),
        ("wind_speed_10m", "mph"),
    ],
)
def test_wrong_units_are_rejected(
    locations, payload_factory, field, wrong_unit
):
    payload = payload_factory(locations[0])
    payload["hourly_units"][field] = wrong_unit

    with pytest.raises(ValueError):
        extractor.validate_payload_structure(payload)


@pytest.mark.parametrize(
    "field, value",
    [
        ("precipitation", -0.1),
        ("wind_speed_10m", -1.0),
        ("temperature_2m", float("nan")),
        ("temperature_2m", float("inf")),
        ("wind_speed_10m", float("-inf")),
        ("temperature_2m", "20"),
        ("precipitation", True),
    ],
)
def test_invalid_weather_values_are_rejected(
    locations, payload_factory, field, value
):
    payload = payload_factory(locations[0])
    payload["hourly"][field][0] = value

    with pytest.raises(ValueError):
        extractor.validate_weather_values(payload["hourly"])


def test_negative_temperature_is_valid(locations, payload_factory):
    payload = payload_factory(locations[0])
    payload["hourly"]["temperature_2m"][0] = -5.0

    counts = extractor.validate_weather_values(payload["hourly"])

    assert counts["temperature_2m"] == 0
    assert payload["hourly"]["temperature_2m"][0] == -5.0


@pytest.mark.parametrize("change", ["duplicate", "gap", "reversed"])
def test_invalid_time_sequence_is_rejected(
    locations, payload_factory, change
):
    payload = payload_factory(locations[0])
    times = payload["hourly"]["time"]

    if change == "duplicate":
        times[1] = times[0]
    elif change == "gap":
        times[1] += 3600
    else:
        times.reverse()

    with pytest.raises(ValueError):
        extractor.parse_forecast_times(payload)


@pytest.mark.parametrize("value", [None, "1791918000", True, 1791918000.0])
def test_invalid_timestamp_type_is_rejected(
    locations, payload_factory, value
):
    payload = payload_factory(locations[0])
    payload["hourly"]["time"][0] = value

    with pytest.raises(ValueError):
        extractor.parse_forecast_times(payload)


@pytest.mark.parametrize(
    "payload",
    [None, [], {"error": True}, {"hourly": {}, "hourly_units": {}}],
)
def test_invalid_payload_structure_is_rejected(payload):
    with pytest.raises(ValueError):
        extractor.validate_payload_structure(payload)


def test_normalization_preserves_position(locations, payload_factory):
    payload = payload_factory(locations[0])
    hourly = payload["hourly"]
    hourly["temperature_2m"][1] = 19.9
    hourly["precipitation"][1] = 0.4
    hourly["wind_speed_10m"][1] = 6.0

    times = extractor.parse_forecast_times(payload)
    records = extractor.normalize_forecasts(
        hourly, times, "run-teste", locations[0]["location_id"]
    )

    assert records[1] == {
        "run_id": "run-teste",
        "location_id": locations[0]["location_id"],
        "forecast_time_utc": times[1].isoformat(),
        "temperature_2m_c": 19.9,
        "precipitation_mm": 0.4,
        "wind_speed_10m_kmh": 6.0,
    }