-- IPL Intelligence — analytical schema (blueprint section 31)
-- Star-schema style: dim_* tables for identity, fact_* tables for events.
-- Designed to be loaded from data/processed/*.parquet once PostgreSQL is
-- available; not required for the Parquet-based analytics/ML pipeline.

CREATE TABLE IF NOT EXISTS dim_player (
    player_id      TEXT PRIMARY KEY,       -- Cricsheet registry id
    display_name   TEXT NOT NULL,
    register_name  TEXT,
    unique_name    TEXT,
    key_cricinfo   TEXT,
    photo_url      TEXT
);

CREATE TABLE IF NOT EXISTS dim_team (
    team_name        TEXT PRIMARY KEY,     -- canonical name, see src/data/team_normalization.py
    team_code        TEXT,
    original_names   TEXT[]                -- historical strings this canonical name absorbs
);

CREATE TABLE IF NOT EXISTS dim_venue (
    venue_id        SERIAL PRIMARY KEY,
    canonical_name  TEXT NOT NULL UNIQUE,
    city            TEXT,
    country         TEXT
);

CREATE TABLE IF NOT EXISTS fact_matches (
    match_id           BIGINT PRIMARY KEY,
    season             TEXT NOT NULL,
    season_year        INT NOT NULL,
    date               DATE NOT NULL,
    event_name         TEXT,
    match_number       INT,
    team1              TEXT REFERENCES dim_team(team_name),
    team2              TEXT REFERENCES dim_team(team_name),
    team1_original     TEXT,   -- name as originally recorded, before normalization (section 42)
    team2_original     TEXT,
    venue              TEXT,
    venue_original     TEXT,  -- name as originally recorded, before normalization (section 43)
    city               TEXT,
    toss_winner        TEXT REFERENCES dim_team(team_name),
    toss_decision      TEXT,
    winner             TEXT REFERENCES dim_team(team_name),
    outcome_type       TEXT,
    result_type        TEXT,
    win_by_runs        INT,
    win_by_wickets     INT,
    method             TEXT,
    player_of_match    TEXT
);

CREATE TABLE IF NOT EXISTS fact_deliveries (
    delivery_id        BIGINT PRIMARY KEY,
    match_id           BIGINT NOT NULL REFERENCES fact_matches(match_id),
    season_year        INT NOT NULL,
    date               DATE NOT NULL,
    venue              TEXT,
    innings            SMALLINT NOT NULL,
    is_super_over      BOOLEAN NOT NULL,
    "over"             SMALLINT NOT NULL,
    ball               SMALLINT NOT NULL,
    phase              TEXT NOT NULL,
    batting_team       TEXT REFERENCES dim_team(team_name),
    bowling_team       TEXT REFERENCES dim_team(team_name),
    batter_id          TEXT REFERENCES dim_player(player_id),
    bowler_id          TEXT REFERENCES dim_player(player_id),
    non_striker_id     TEXT REFERENCES dim_player(player_id),
    runs_batter        SMALLINT NOT NULL,
    runs_extras        SMALLINT NOT NULL,
    runs_total         SMALLINT NOT NULL,
    extra_wides        SMALLINT NOT NULL DEFAULT 0,
    extra_noballs      SMALLINT NOT NULL DEFAULT 0,
    extra_byes         SMALLINT NOT NULL DEFAULT 0,
    extra_legbyes      SMALLINT NOT NULL DEFAULT 0,
    extra_penalty      SMALLINT NOT NULL DEFAULT 0,
    is_wicket          SMALLINT NOT NULL DEFAULT 0,
    player_dismissed_id TEXT REFERENCES dim_player(player_id),
    dismissal_kind     TEXT
);

CREATE TABLE IF NOT EXISTS fact_batting (
    player_id             TEXT PRIMARY KEY REFERENCES dim_player(player_id),
    innings               INT,
    runs                  INT,
    balls_faced           INT,
    batting_average        NUMERIC,
    strike_rate           NUMERIC,
    fours                 INT,
    sixes                 INT,
    fifties               INT,
    hundreds              INT,
    boundary_pct          NUMERIC,
    dot_ball_pct          NUMERIC
);

CREATE TABLE IF NOT EXISTS fact_bowling (
    player_id             TEXT PRIMARY KEY REFERENCES dim_player(player_id),
    balls_bowled          INT,
    overs                 NUMERIC,
    runs_conceded         INT,
    wickets               INT,
    economy               NUMERIC,
    bowling_average       NUMERIC,
    bowling_strike_rate   NUMERIC,
    dot_ball_pct          NUMERIC,
    boundary_conceded_pct NUMERIC
);

-- Populated once the win-probability model exists; links a prediction back
-- to the exact ball and the model version that produced it.
CREATE TABLE IF NOT EXISTS fact_predictions (
    prediction_id      BIGSERIAL PRIMARY KEY,
    delivery_id        BIGINT NOT NULL REFERENCES fact_deliveries(delivery_id),
    match_id           BIGINT NOT NULL REFERENCES fact_matches(match_id),
    model_version       TEXT NOT NULL,
    batting_team_win_prob NUMERIC NOT NULL,
    predicted_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_deliveries_match ON fact_deliveries(match_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_batter ON fact_deliveries(batter_id);
CREATE INDEX IF NOT EXISTS idx_deliveries_bowler ON fact_deliveries(bowler_id);
CREATE INDEX IF NOT EXISTS idx_matches_season ON fact_matches(season_year);
CREATE INDEX IF NOT EXISTS idx_predictions_delivery ON fact_predictions(delivery_id);
