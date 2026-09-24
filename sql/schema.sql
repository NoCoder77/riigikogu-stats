CREATE TABLE IF NOT EXISTS persons (
    id TEXT PRIMARY KEY,
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    birth_date DATE,
    raw JSONB
);

CREATE TABLE IF NOT EXISTS terms (
    id TEXT PRIMARY KEY,
    name TEXT,
    start_date DATE,
    end_date DATE,
    raw JSONB
);

CREATE TABLE IF NOT EXISTS factions (
    id TEXT PRIMARY KEY,
    name TEXT,
    raw JSONB
);

CREATE TABLE IF NOT EXISTS sessions (
    id TEXT PRIMARY KEY,
    term_id TEXT REFERENCES terms(id),
    session_date DATE,
    title TEXT,
    raw JSONB
);

CREATE TABLE IF NOT EXISTS session_attendance (
    session_id TEXT REFERENCES sessions(id),
    person_id TEXT REFERENCES persons(id),
    status TEXT,
    raw JSONB,
    PRIMARY KEY (session_id, person_id)
);

CREATE TABLE IF NOT EXISTS votes (
    id TEXT PRIMARY KEY,
    session_id TEXT REFERENCES sessions(id),
    title TEXT,
    subject TEXT,
    vote_type TEXT,
    result TEXT,
    vote_time TIMESTAMPTZ,
    raw JSONB
);

CREATE TABLE IF NOT EXISTS vote_casts (
    vote_id TEXT REFERENCES votes(id),
    person_id TEXT REFERENCES persons(id),
    choice TEXT,
    raw JSONB,
    PRIMARY KEY (vote_id, person_id)
);

CREATE TABLE IF NOT EXISTS import_runs (
    id BIGSERIAL PRIMARY KEY,
    started_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    finished_at TIMESTAMPTZ,
    start_date DATE NOT NULL,
    end_date DATE NOT NULL,
    step_days INTEGER NOT NULL,
    only_votings BOOLEAN NOT NULL DEFAULT FALSE,
    only_sittings BOOLEAN NOT NULL DEFAULT FALSE,
    status TEXT NOT NULL DEFAULT 'running',
    items_processed INTEGER NOT NULL DEFAULT 0,
    items_skipped INTEGER NOT NULL DEFAULT 0,
    error_message TEXT
);

CREATE TABLE IF NOT EXISTS import_item_hashes (
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    content_hash TEXT NOT NULL,
    last_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    PRIMARY KEY (entity_type, entity_id)
);

CREATE TABLE IF NOT EXISTS person_faction_membership (
    person_id TEXT REFERENCES persons(id),
    faction_id TEXT REFERENCES factions(id),
    start_date DATE,
    end_date DATE,
    raw JSONB,
    PRIMARY KEY (person_id, faction_id, start_date)
);

CREATE INDEX IF NOT EXISTS idx_sessions_date ON sessions (session_date);
CREATE INDEX IF NOT EXISTS idx_votes_session ON votes (session_id);
CREATE INDEX IF NOT EXISTS idx_votes_time ON votes (vote_time);
CREATE INDEX IF NOT EXISTS idx_attendance_person ON session_attendance (person_id);
CREATE INDEX IF NOT EXISTS idx_casts_person ON vote_casts (person_id);
CREATE INDEX IF NOT EXISTS idx_import_runs_dates ON import_runs (start_date, end_date);