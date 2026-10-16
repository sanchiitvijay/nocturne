-- NOCTURNE schema. Idempotent: safe to run on every start.

CREATE TABLE IF NOT EXISTS meta (
    key   TEXT PRIMARY KEY,
    value TEXT
);

-- People & access ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS users (
    id            INTEGER PRIMARY KEY,
    username      TEXT NOT NULL UNIQUE COLLATE NOCASE,
    display_name  TEXT,
    password_hash TEXT NOT NULL,
    role          TEXT NOT NULL,
    active        INTEGER NOT NULL DEFAULT 1,
    must_change   INTEGER NOT NULL DEFAULT 0,
    created_at    TEXT NOT NULL,
    last_login_at TEXT
);

-- Server-side sessions: the cookie carries only the id, so sign-out, password changes and resets take effect at once.
CREATE TABLE IF NOT EXISTS sessions (
    id         TEXT PRIMARY KEY,
    user_id    INTEGER NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    created_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    ip         TEXT
);
CREATE INDEX IF NOT EXISTS ix_sessions_user ON sessions(user_id);

CREATE TABLE IF NOT EXISTS audit_log (
    id       INTEGER PRIMARY KEY,
    at       TEXT NOT NULL,
    user_id  INTEGER,
    username TEXT,
    action   TEXT NOT NULL,
    target   TEXT,
    detail   TEXT,
    ip       TEXT
);
CREATE INDEX IF NOT EXISTS ix_audit_at ON audit_log(at DESC);

-- Network inventory ----------------------------------------------------------
CREATE TABLE IF NOT EXISTS sites (
    code       TEXT PRIMARY KEY,         -- canonical, zero-padded site/FEI code
    label      TEXT,                     -- "Dallas, TX"
    city       TEXT,
    state      TEXT,
    address    TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS devices (
    id           INTEGER PRIMARY KEY,
    name         TEXT NOT NULL,
    name_key     TEXT NOT NULL UNIQUE,   -- lower-cased name, the identity used for matching
    ip           TEXT,
    node_id      INTEGER,
    site_code    TEXT,
    role         TEXT,
    machine_type TEXT,
    vendor       TEXT,
    location     TEXT,
    first_seen   TEXT,
    last_seen    TEXT,
    last_status  INTEGER,
    event_count  INTEGER NOT NULL DEFAULT 0,
    extra        TEXT
);
CREATE INDEX IF NOT EXISTS ix_devices_ip   ON devices(ip);
CREATE INDEX IF NOT EXISTS ix_devices_site ON devices(site_code);
CREATE INDEX IF NOT EXISTS ix_devices_role ON devices(role);

-- Event catalogue: name/severity/category overrides set by admins win over rules.
CREATE TABLE IF NOT EXISTS event_types (
    type_id     INTEGER PRIMARY KEY,
    name        TEXT,
    source_name TEXT,                    -- name as it arrived in the export
    severity    TEXT,                    -- NULL = decided by classification rules
    category    TEXT,                    -- NULL = decided by classification rules
    sample      TEXT,
    updated_at  TEXT
);

-- Alerts / events ----------------------------------------------------------------
CREATE TABLE IF NOT EXISTS events (
    id          INTEGER PRIMARY KEY,
    source      TEXT NOT NULL DEFAULT 'import',   -- import | simulation | custom
    source_id   INTEGER NOT NULL,                 -- EventID from the monitoring tool
    ts          TEXT,                             -- ISO timestamp "YYYY-MM-DD HH:MM:SS.fff"
    type_id     INTEGER,
    name        TEXT,
    message     TEXT,
    device_id   INTEGER REFERENCES devices(id),
    device_name TEXT,
    ip          TEXT,
    site_code   TEXT,
    status_code INTEGER,
    severity    TEXT,
    category    TEXT,
    actionable  INTEGER NOT NULL DEFAULT 0,
    transition  TEXT,                             -- down | up | NULL
    pair_key    TEXT,                             -- links a "down" with its matching "up"
    state       TEXT NOT NULL DEFAULT 'new',      -- new | acknowledged | resolved
    owner       TEXT,
    state_note  TEXT,
    state_at    TEXT,
    job_id      TEXT,
    created_at  TEXT,
    extra       TEXT,
    UNIQUE(source, source_id)
);
-- Indexes follow the console's access paths. Most are covering (they hold every column the query reads), so the
-- dashboard aggregates, facet counts, outage pairing and site roll-ups scan an index instead of visiting each row.
DROP INDEX IF EXISTS ix_events_ts;
DROP INDEX IF EXISTS ix_events_chrono;   -- replaced by ix_events_time (same order, covering)
DROP INDEX IF EXISTS ix_events_sev;      -- replaced by ix_events_sev_time
DROP INDEX IF EXISTS ix_events_act_ts;   -- replaced by ix_events_act_time
DROP INDEX IF EXISTS ix_events_pair;     -- replaced by ix_events_pair_cov
DROP INDEX IF EXISTS ix_events_site_ts;  -- replaced by ix_events_site_cov
-- Time order (minute-precision times: EventID breaks ties) plus the columns the dashboard aggregates read.
CREATE INDEX IF NOT EXISTS ix_events_time      ON events(ts, source_id, severity, category, actionable, state, source, device_id, site_code, type_id, name);
CREATE INDEX IF NOT EXISTS ix_events_device_ts ON events(device_id, ts);
CREATE INDEX IF NOT EXISTS ix_events_site_cov  ON events(site_code, ts, actionable, severity);
CREATE INDEX IF NOT EXISTS ix_events_sev_time  ON events(severity, ts DESC, source_id DESC);
CREATE INDEX IF NOT EXISTS ix_events_type      ON events(type_id);
CREATE INDEX IF NOT EXISTS ix_events_state     ON events(state);
CREATE INDEX IF NOT EXISTS ix_events_ip        ON events(ip);
CREATE INDEX IF NOT EXISTS ix_events_act_time  ON events(actionable, ts DESC, source_id DESC);
-- Alert-console facet counts (severity, category, state, source) for the actionable switch.
CREATE INDEX IF NOT EXISTS ix_events_facets    ON events(actionable, severity, category, state, source, ts);
-- Outage pairing walks down/up transitions by pair key in time order.
CREATE INDEX IF NOT EXISTS ix_events_pair_cov  ON events(pair_key, ts, source_id, transition, device_id, name) WHERE transition IS NOT NULL;

CREATE VIRTUAL TABLE IF NOT EXISTS events_fts USING fts5(
    name, message, device_name, content='events', content_rowid='id'
);

-- Service-desk history -------------------------------------------------------------
CREATE TABLE IF NOT EXISTS tickets (
    id                INTEGER PRIMARY KEY,
    number            TEXT NOT NULL UNIQUE,
    kind              TEXT,                -- INC / RITM / TASK / CHG / …
    state             TEXT,
    is_open           INTEGER NOT NULL DEFAULT 1,
    priority          TEXT,
    category          TEXT,
    opened_by         TEXT,
    assigned_to       TEXT,
    assignment_group  TEXT,
    created_at        TEXT,
    updated_at        TEXT,
    closed_at         TEXT,
    resolve_minutes   INTEGER,
    incident_start    TEXT,                -- start time stated in the ticket text, validated against created_at
    short_description TEXT,
    description       TEXT,
    work_notes        TEXT,
    work_notes_list   TEXT,
    close_notes       TEXT,
    cmdb_ci           TEXT,
    resolution        TEXT,                -- best "what fixed it" summary
    sites             TEXT,                -- JSON list of site codes found in the text
    ips               TEXT,                -- JSON list of IPv4 addresses found in the text
    devices           TEXT,                -- JSON list of device names found in the text
    job_id            TEXT,
    extra             TEXT
);
CREATE INDEX IF NOT EXISTS ix_tickets_created ON tickets(created_at DESC);
CREATE INDEX IF NOT EXISTS ix_tickets_open    ON tickets(is_open);

CREATE VIRTUAL TABLE IF NOT EXISTS tickets_fts USING fts5(
    number, short_description, description, work_notes, close_notes,
    content='tickets', content_rowid='id'
);

CREATE TABLE IF NOT EXISTS ticket_links (
    id         INTEGER PRIMARY KEY,
    ticket_id  INTEGER NOT NULL REFERENCES tickets(id) ON DELETE CASCADE,
    kind       TEXT NOT NULL,             -- ci | device | ip | site
    value      TEXT NOT NULL,
    device_id  INTEGER NOT NULL DEFAULT 0,
    site_code  TEXT,
    confidence REAL NOT NULL,
    evidence    TEXT,                     -- confirmed | no_alerts | NULL (events do not cover the ticket's opening)
    gap_minutes INTEGER,                  -- confirming alert to ticket opening, minutes (positive = alert first)
    event_id    INTEGER,                  -- the confirming alert
    UNIQUE(ticket_id, kind, value, device_id)
);
CREATE INDEX IF NOT EXISTS ix_links_device ON ticket_links(device_id);
CREATE INDEX IF NOT EXISTS ix_links_site   ON ticket_links(site_code);

-- Import jobs ------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jobs (
    id          TEXT PRIMARY KEY,
    dataset     TEXT,                     -- events | tickets | unknown
    filename    TEXT,
    stored_path TEXT,
    size_bytes  INTEGER,
    status      TEXT NOT NULL,            -- staged | queued | running | succeeded | failed | interrupted | cancelled
    progress    REAL NOT NULL DEFAULT 0,
    stage       TEXT,
    message     TEXT,
    preview     TEXT,                     -- JSON: detected headers, sample rows, proposed mapping
    mapping     TEXT,                     -- JSON: field → column index
    options     TEXT,                     -- JSON: import options
    stats       TEXT,                     -- JSON quality report
    created_by  TEXT,
    created_at  TEXT,
    started_at  TEXT,
    finished_at TEXT
);

CREATE TABLE IF NOT EXISTS job_rejects (
    id      INTEGER PRIMARY KEY,
    job_id  TEXT NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
    row_no  INTEGER,
    reason  TEXT,
    raw     TEXT
);
CREATE INDEX IF NOT EXISTS ix_rejects_job ON job_rejects(job_id);

-- Learning loop -------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS feedback (
    id            INTEGER PRIMARY KEY,
    event_id      INTEGER NOT NULL,
    username      TEXT,
    verdict       TEXT NOT NULL,          -- helpful | not_helpful
    ticket_number TEXT,
    note          TEXT,
    created_at    TEXT
);
CREATE INDEX IF NOT EXISTS ix_feedback_event ON feedback(event_id);

-- Gemini answers, cached by a fingerprint of the evidence they were based on.
CREATE TABLE IF NOT EXISTS ai_insights (
    cache_key   TEXT PRIMARY KEY,
    event_id    INTEGER NOT NULL,
    model       TEXT,
    payload     TEXT NOT NULL,
    latency_ms  INTEGER,
    hits        INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT NOT NULL,
    last_hit_at TEXT
);
CREATE INDEX IF NOT EXISTS ix_ai_event ON ai_insights(event_id);
