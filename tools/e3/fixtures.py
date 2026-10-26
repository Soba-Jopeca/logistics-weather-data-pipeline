"""Deterministic synthetic bytes; real validators remain authoritative."""
from datetime import date
import json
from scripts.weather_window import build_cycle_window
from tools.e3.preflight import GateError


def build_valid_payload(location, cycle_date):
    window = build_cycle_window(date.fromisoformat(cycle_date), location['timezone'])
    times = [int(t.timestamp()) for t in window['expected_times_utc']]
    return {'timezone': 'GMT', 'utc_offset_seconds': 0,
            'hourly_units': {'time': 'unixtime', 'temperature_2m': '°C', 'precipitation': 'mm', 'wind_speed_10m': 'km/h'},
            'hourly': {'time': times, 'temperature_2m': [20.0] * len(times),
                       'precipitation': [0.0] * len(times), 'wind_speed_10m': [5.0] * len(times)}}


def fixture_bytes(location, cycle_date, fault='none'):
    value = build_valid_payload(location, cycle_date)
    if fault == 'null':
        value['hourly']['temperature_2m'][0] = None
    elif fault == 'corrupt':
        return b'{invalid-json'
    elif fault != 'none':
        raise GateError('Unknown fixture fault')
    return json.dumps(value, ensure_ascii=False, allow_nan=False).encode()
