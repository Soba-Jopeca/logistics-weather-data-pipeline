-- Additive staging extension. Apply explicitly only to disposable weather_test during S05.
ALTER TABLE weather_mvp.weather_runs
    ADD CONSTRAINT weather_runs_batch_run_location_unique
    UNIQUE (batch_id, run_id, location_id);

CREATE TABLE weather_mvp.weather_raw_staging (
    batch_id UUID NOT NULL,
    run_id UUID NOT NULL,
    location_id TEXT NOT NULL,
    raw_path TEXT NOT NULL,
    raw_sha256 CHAR(64) NOT NULL CHECK (raw_sha256 ~ '^[0-9a-f]{64}$'),
    raw_payload JSONB NOT NULL CHECK (jsonb_typeof(raw_payload) = 'object'),
    ingested_at TIMESTAMPTZ NOT NULL DEFAULT transaction_timestamp(),
    PRIMARY KEY (run_id, location_id),
    FOREIGN KEY (batch_id, run_id, location_id)
        REFERENCES weather_mvp.weather_runs(batch_id, run_id, location_id)
);
CREATE INDEX weather_raw_staging_batch_idx
    ON weather_mvp.weather_raw_staging(batch_id);
INSERT INTO weather_mvp.schema_migrations(version)
VALUES ('002_weather_raw_staging')
ON CONFLICT (version) DO NOTHING;
