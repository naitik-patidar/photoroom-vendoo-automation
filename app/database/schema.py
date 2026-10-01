"""
Database schema definitions and migration management.

Tables:
- products: tracks individual product records
- jobs: tracks processing jobs with full status history

Uses SQLite via stdlib sqlite3. No ORM — plain SQL for simplicity and transparency.
"""

# ---------------------------------------------------------------------------
# Schema SQL
# ---------------------------------------------------------------------------

CREATE_PRODUCTS_TABLE = """
CREATE TABLE IF NOT EXISTS products (
    product_id      TEXT PRIMARY KEY,
    sku             TEXT,
    title           TEXT,
    description     TEXT,
    brand           TEXT,
    category        TEXT,
    subcategory     TEXT,
    size            TEXT,
    color           TEXT,
    material        TEXT,
    condition       TEXT,
    price           REAL,
    currency        TEXT DEFAULT 'USD',
    tags            TEXT,       -- JSON array stored as string
    quantity        INTEGER DEFAULT 1,
    created_at      TEXT NOT NULL,
    updated_at      TEXT NOT NULL
);
"""

CREATE_JOBS_TABLE = """
CREATE TABLE IF NOT EXISTS jobs (
    job_id              TEXT PRIMARY KEY,
    product_id          TEXT,
    original_file       TEXT NOT NULL,
    processed_file      TEXT,
    status              TEXT NOT NULL DEFAULT 'QUEUED',
    photoroom_status    TEXT,
    listing_status      TEXT,
    vendoo_status       TEXT,
    retry_count         INTEGER DEFAULT 0,
    error_message       TEXT,
    created_at          TEXT NOT NULL,
    updated_at          TEXT NOT NULL,
    FOREIGN KEY (product_id) REFERENCES products(product_id)
);
"""

CREATE_JOB_HISTORY_TABLE = """
CREATE TABLE IF NOT EXISTS job_history (
    history_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    job_id          TEXT NOT NULL,
    old_status      TEXT,
    new_status      TEXT NOT NULL,
    note            TEXT,
    occurred_at     TEXT NOT NULL,
    FOREIGN KEY (job_id) REFERENCES jobs(job_id)
);
"""

# Indexes for common query patterns
CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_product_id ON jobs(product_id);",
    "CREATE INDEX IF NOT EXISTS idx_jobs_created_at ON jobs(created_at);",
    "CREATE INDEX IF NOT EXISTS idx_job_history_job_id ON job_history(job_id);",
]

ALL_MIGRATIONS = [
    CREATE_PRODUCTS_TABLE,
    CREATE_JOBS_TABLE,
    CREATE_JOB_HISTORY_TABLE,
    *CREATE_INDEXES,
]

SCHEMA_VERSION = 1
