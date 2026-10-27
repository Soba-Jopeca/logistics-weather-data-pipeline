CREATE SCHEMA IF NOT EXISTS weather_mvp;

CREATE TABLE IF NOT EXISTS weather_mvp.schema_migrations (
    version TEXT PRIMARY KEY,
    applied_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp()
);

CREATE TABLE IF NOT EXISTS weather_mvp.locations (
    location_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    timezone TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS weather_mvp.weather_batches (
    batch_id UUID PRIMARY KEY,
    cycle_date_local DATE NOT NULL,
    timezone TEXT NOT NULL,
    window_start_utc TIMESTAMPTZ NOT NULL,
    window_end_utc TIMESTAMPTZ NOT NULL,
    batch_status TEXT NOT NULL CHECK (
        batch_status IN ('success', 'partial_success', 'failed')
    ),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL CHECK (ended_at >= started_at),
    manifest_path TEXT NOT NULL,
    manifest_sha256 CHAR(64) NOT NULL CHECK (manifest_sha256 ~ '^[0-9a-f]{64}$'),
    batch_report_path TEXT NOT NULL,
    batch_report_sha256 CHAR(64) NOT NULL CHECK (batch_report_sha256 ~ '^[0-9a-f]{64}$'),
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    CHECK (window_end_utc > window_start_utc),
    UNIQUE (batch_id, cycle_date_local)
);

CREATE TABLE IF NOT EXISTS weather_mvp.weather_runs (
    run_id UUID PRIMARY KEY,
    batch_id UUID NOT NULL REFERENCES weather_mvp.weather_batches(batch_id),
    location_id TEXT NOT NULL REFERENCES weather_mvp.locations(location_id),
    location_name TEXT NOT NULL,
    latitude DOUBLE PRECISION NOT NULL CHECK (latitude BETWEEN -90 AND 90),
    longitude DOUBLE PRECISION NOT NULL CHECK (longitude BETWEEN -180 AND 180),
    timezone TEXT NOT NULL,
    requested_at TIMESTAMPTZ NOT NULL,
    collected_at TIMESTAMPTZ,
    source TEXT NOT NULL,
    endpoint TEXT NOT NULL,
    request_params JSONB NOT NULL,
    raw_path TEXT,
    raw_sha256 CHAR(64),
    report_path TEXT NOT NULL,
    report_sha256 CHAR(64) NOT NULL CHECK (report_sha256 ~ '^[0-9a-f]{64}$'),
    run_status TEXT NOT NULL CHECK (
        run_status IN ('validated', 'validated_with_nulls', 'incomplete', 'failed')
    ),
    validation JSONB,
    CHECK ((raw_path IS NULL) = (raw_sha256 IS NULL)),
    CHECK (raw_sha256 IS NULL OR raw_sha256 ~ '^[0-9a-f]{64}$'),
    UNIQUE (run_id, location_id),
    UNIQUE (batch_id, location_id)
);

CREATE TABLE IF NOT EXISTS weather_mvp.weather_attempts (
    attempt_id UUID PRIMARY KEY,
    run_id UUID NOT NULL REFERENCES weather_mvp.weather_runs(run_id),
    attempt_no SMALLINT NOT NULL CHECK (attempt_no BETWEEN 1 AND 3),
    started_at TIMESTAMPTZ NOT NULL,
    ended_at TIMESTAMPTZ NOT NULL CHECK (ended_at >= started_at),
    duration_ms NUMERIC(12, 3) NOT NULL CHECK (duration_ms >= 0),
    http_status SMALLINT CHECK (http_status BETWEEN 100 AND 599),
    error_category TEXT,
    error_message TEXT,
    UNIQUE (run_id, attempt_no)
);

CREATE TABLE IF NOT EXISTS weather_mvp.weather_forecasts (
    run_id UUID NOT NULL,
    location_id TEXT NOT NULL,
    forecast_time_utc TIMESTAMPTZ NOT NULL,
    temperature_2m_c DOUBLE PRECISION,
    precipitation_mm DOUBLE PRECISION CHECK (
        precipitation_mm IS NULL OR precipitation_mm >= 0
    ),
    wind_speed_10m_kmh DOUBLE PRECISION CHECK (
        wind_speed_10m_kmh IS NULL OR wind_speed_10m_kmh >= 0
    ),
    PRIMARY KEY (run_id, location_id, forecast_time_utc),
    FOREIGN KEY (run_id, location_id)
        REFERENCES weather_mvp.weather_runs(run_id, location_id)
);

CREATE TABLE IF NOT EXISTS weather_mvp.weather_batch_artifacts (
    batch_id UUID NOT NULL REFERENCES weather_mvp.weather_batches(batch_id),
    artifact_path TEXT NOT NULL,
    artifact_type TEXT NOT NULL CHECK (
        artifact_type IN ('manifest', 'batch_report', 'run_report', 'raw', 'orchestration')
    ),
    sha256 CHAR(64) NOT NULL CHECK (sha256 ~ '^[0-9a-f]{64}$'),
    size_bytes BIGINT NOT NULL CHECK (size_bytes >= 0),
    PRIMARY KEY (batch_id, artifact_path)
);

CREATE TABLE IF NOT EXISTS weather_mvp.weather_publications (
    run_id UUID NOT NULL,
    location_id TEXT NOT NULL,
    product_type TEXT NOT NULL CHECK (
        product_type IN (
            'temperature_2m',
            'precipitation',
            'wind_speed_10m',
            'hourly_bundle'
        )
    ),
    status TEXT NOT NULL CHECK (status IN ('published', 'unavailable')),
    published_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    quality_reasons TEXT[] NOT NULL DEFAULT ARRAY[]::TEXT[],
    PRIMARY KEY (run_id, location_id, product_type),
    FOREIGN KEY (run_id, location_id)
        REFERENCES weather_mvp.weather_runs(run_id, location_id)
);

INSERT INTO weather_mvp.schema_migrations (version)
VALUES ('001_weather_schema')
ON CONFLICT (version) DO NOTHING;
