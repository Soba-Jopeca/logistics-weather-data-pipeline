WITH parameters AS (
    SELECT
        %s::TEXT AS location_id,
        %s::TIMESTAMPTZ AS as_of_at,
        %s::TEXT AS product_type
),
target_location AS (
    SELECT location.*
    FROM weather_mvp.locations AS location
    JOIN parameters AS params USING (location_id)
),
publication_versions AS (
    SELECT
        publication.run_id,
        publication.location_id,
        publication.product_type,
        publication.status AS publication_status,
        publication.published_at,
        publication.quality_reasons,
        run.batch_id,
        run.run_status,
        run.collected_at,
        batch.window_start_utc,
        batch.window_end_utc
    FROM weather_mvp.weather_publications AS publication
    JOIN weather_mvp.weather_runs AS run
      ON run.run_id = publication.run_id
     AND run.location_id = publication.location_id
    JOIN weather_mvp.weather_batches AS batch
      ON batch.batch_id = run.batch_id
    JOIN parameters AS params
      ON params.location_id = publication.location_id
     AND params.product_type = publication.product_type
    WHERE publication.published_at <= params.as_of_at
),
latest_version AS (
    SELECT DISTINCT ON (product_type) *
    FROM publication_versions
    ORDER BY product_type, published_at DESC, collected_at DESC NULLS LAST, run_id
),
candidate_coverage AS (
    SELECT
        version.*,
        coverage.expected_count,
        coverage.complete_count
    FROM publication_versions AS version
    JOIN parameters AS params ON TRUE
    CROSS JOIN LATERAL (
        SELECT
            COUNT(*) AS expected_count,
            COUNT(*) FILTER (
                WHERE forecast.forecast_time_utc IS NOT NULL
                  AND CASE params.product_type
                      WHEN 'temperature_2m'
                          THEN forecast.temperature_2m_c IS NOT NULL
                      WHEN 'precipitation'
                          THEN forecast.precipitation_mm IS NOT NULL
                      WHEN 'wind_speed_10m'
                          THEN forecast.wind_speed_10m_kmh IS NOT NULL
                      WHEN 'hourly_bundle'
                          THEN forecast.temperature_2m_c IS NOT NULL
                           AND forecast.precipitation_mm IS NOT NULL
                           AND forecast.wind_speed_10m_kmh IS NOT NULL
                      ELSE FALSE
                  END
            ) AS complete_count
        FROM generate_series(
            GREATEST(
                version.window_start_utc,
                date_trunc('hour', version.collected_at AT TIME ZONE 'UTC')
                    AT TIME ZONE 'UTC'
                    + CASE
                        WHEN version.collected_at = (
                            date_trunc('hour', version.collected_at AT TIME ZONE 'UTC')
                            AT TIME ZONE 'UTC'
                        )
                            THEN INTERVAL '0 hours'
                        ELSE INTERVAL '1 hour'
                      END
            ),
            version.window_end_utc - INTERVAL '1 hour',
            INTERVAL '1 hour'
        ) AS expected(forecast_time_utc)
        LEFT JOIN weather_mvp.weather_forecasts AS forecast
          ON forecast.run_id = version.run_id
         AND forecast.location_id = version.location_id
         AND forecast.forecast_time_utc = expected.forecast_time_utc
    ) AS coverage
),
eligible_versions AS (
    SELECT coverage.*
    FROM candidate_coverage AS coverage
    JOIN parameters AS params ON TRUE
    WHERE coverage.publication_status = 'published'
      AND coverage.run_status IN ('validated', 'validated_with_nulls')
      AND coverage.collected_at IS NOT NULL
      AND coverage.collected_at <= params.as_of_at
      AND coverage.collected_at >= params.as_of_at - INTERVAL '3 hours'
      AND coverage.expected_count > 0
      AND coverage.complete_count = coverage.expected_count
),
selected_version AS (
    SELECT DISTINCT ON (product_type) *
    FROM eligible_versions
    ORDER BY product_type, collected_at DESC, published_at DESC, run_id
)
SELECT
    location.location_id,
    location.name AS location_name,
    params.product_type,
    params.as_of_at,
    CASE
        WHEN selected.run_id IS NULL THEN 'unavailable'
        WHEN forecast.forecast_time_utc IS NULL THEN 'no_future_forecast'
        ELSE 'available'
    END AS data_status,
    selected.run_id,
    selected.batch_id,
    selected.collected_at,
    selected.published_at,
    (selected.run_id IS NOT NULL AND latest.run_id IS DISTINCT FROM selected.run_id)
        AS fallback_used,
    CASE
        WHEN selected.run_id IS NOT NULL
         AND latest.run_id IS DISTINCT FROM selected.run_id
            THEN 'latest_version_ineligible'
        WHEN selected.run_id IS NOT NULL THEN NULL
        WHEN latest.run_id IS NULL THEN 'no_published_version'
        WHEN latest.publication_status <> 'published' THEN 'latest_version_unavailable'
        WHEN latest.collected_at IS NULL OR latest.collected_at > params.as_of_at
            THEN 'latest_version_not_collected_as_of'
        WHEN latest.collected_at < params.as_of_at - INTERVAL '3 hours'
            THEN 'latest_version_stale'
        ELSE 'latest_version_incomplete'
    END AS availability_reason,
    forecast.forecast_time_utc,
    forecast.temperature_2m_c,
    forecast.precipitation_mm,
    forecast.wind_speed_10m_kmh
FROM target_location AS location
CROSS JOIN parameters AS params
LEFT JOIN selected_version AS selected
  ON selected.location_id = location.location_id
 AND selected.product_type = params.product_type
LEFT JOIN latest_version AS latest
  ON latest.location_id = location.location_id
 AND latest.product_type = params.product_type
LEFT JOIN weather_mvp.weather_forecasts AS forecast
  ON forecast.run_id = selected.run_id
 AND forecast.location_id = selected.location_id
 AND forecast.forecast_time_utc >= params.as_of_at
 AND forecast.forecast_time_utc < selected.window_end_utc
ORDER BY forecast.forecast_time_utc;
