CREATE TABLE IF NOT EXISTS timeline_entries (
    id TEXT PRIMARY KEY,
    date TEXT,
    type TEXT CHECK(type IN ('diary', 'photo')),
    content TEXT,
    source_path TEXT
);

CREATE TABLE IF NOT EXISTS gaps (
    id TEXT PRIMARY KEY,
    start_date TEXT,
    end_date TEXT,
    gap_days INTEGER
);

CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    gap_id TEXT,
    memory_text TEXT,
    why_this_is_false TEXT,
    rationale TEXT,
    word_count INTEGER,
    is_fabricated BOOLEAN
);
