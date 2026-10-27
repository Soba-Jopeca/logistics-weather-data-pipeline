-- Parameter: batch_id UUID. Normalize Open-Meteo unixtime arrays from verified JSONB.
-- SQL is intentionally strict about row cardinality; Python validates exact values
-- and UTC timestamps against independently normalized records before COMMIT.
INSERT INTO weather_mvp.weather_forecasts (
    run_id, location_id, forecast_time_utc,
    temperature_2m_c, precipitation_mm, wind_speed_10m_kmh
)
SELECT
    s.run_id,
    s.location_id,
    to_timestamp((v.time_value #>> '{}')::DOUBLE PRECISION),
    (s.raw_payload #>> ARRAY['hourly','temperature_2m', (v.ordinality-1)::TEXT])::DOUBLE PRECISION,
    (s.raw_payload #>> ARRAY['hourly','precipitation', (v.ordinality-1)::TEXT])::DOUBLE PRECISION,
    (s.raw_payload #>> ARRAY['hourly','wind_speed_10m', (v.ordinality-1)::TEXT])::DOUBLE PRECISION
FROM weather_mvp.weather_raw_staging AS s
CROSS JOIN LATERAL jsonb_array_elements(s.raw_payload #> '{hourly,time}')
    WITH ORDINALITY AS v(time_value, ordinality)
WHERE s.batch_id = %s
  AND (s.raw_payload #>> '{hourly_units,time}') = 'unixtime'
  AND (s.raw_payload #>> '{timezone}') = 'GMT'
  AND (s.raw_payload #>> '{utc_offset_seconds}')::INTEGER = 0
  AND jsonb_array_length(s.raw_payload #> '{hourly,time}')
      = jsonb_array_length(s.raw_payload #> '{hourly,temperature_2m}')
  AND jsonb_array_length(s.raw_payload #> '{hourly,time}')
      = jsonb_array_length(s.raw_payload #> '{hourly,precipitation}')
  AND jsonb_array_length(s.raw_payload #> '{hourly,time}')
      = jsonb_array_length(s.raw_payload #> '{hourly,wind_speed_10m}')
  AND (s.raw_payload #>> '{hourly_units,temperature_2m}') = '°C'
  AND (s.raw_payload #>> '{hourly_units,precipitation}') = 'mm'
  AND (s.raw_payload #>> '{hourly_units,wind_speed_10m}') = 'km/h'
ON CONFLICT (run_id, location_id, forecast_time_utc) DO NOTHING;
