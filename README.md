# Pulse — Personal News Intelligence System

> **"Your world. Filtered intelligently."**

Pulse is a production-quality personal news intelligence platform designed for technology and systems engineering professionals. Rather than acting as a generic aggregator or raw RSS reader, Pulse continuously collects news from multiple permitted sources, understands what each story is about, eliminates redundant duplicate coverage, categorizes events, determines objective importance, personalizes delivery according to the user's technical interests, and presents only the information that truly matters.

---

## Phase 2 Milestone: Real News Ingestion Pipeline

Pulse now features a production-ready, maintainable real news ingestion layer that replaces mock datasets with live feeds from verified sources.

```text
Permitted Public Sources (8 Registered Feeds)
                     │
                     ▼
    ┌──────────────────────────────────┐
    │         Source Registry          │  (backend/app/services/source_registry.py)
    │  (Centralized source catalogue)  │
    └────────────────┬─────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────┐
    │          Feed Fetcher            │  (backend/app/services/feed_fetcher.py)
    │  (Async HTTP via httpx, timeouts)│  (Per-source error isolation)
    └────────────────┬─────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────┐
    │       Article Normalizer         │  (backend/app/services/article_normalizer.py)
    │  (Canonical URLs, HTML strip)    │  (UTC timestamps, content hashing)
    └────────────────┬─────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────┐
    │       Duplicate Detection        │  (backend/app/services/duplicate_detector.py)
    │  (Deterministic URL & ID match)  │  (Zero duplicate insertion)
    └────────────────┬─────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────┐
    │       Database Repository        │  (backend/app/core/db_repository.py)
    │  (SQLite dev / PostgreSQL prod)  │  (Indexed URLs, categories, dates)
    └────────────────┬─────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────┐
    │       FastAPI REST Endpoints     │  (POST /api/ingestion/run)
    │  (/api/news, /api/stories)       │  (GET  /api/ingestion/sources)
    └────────────────┬─────────────────┘
                     │
                     ▼
    ┌──────────────────────────────────┐
    │       React Frontend Feed        │  (Surfaces live ingested news)
    │  (Instant sync & empty states)   │  (External links to original reporting)
    └──────────────────────────────────┘
```

---

## Registered Public Sources

Pulse starts with 8 legitimate, accessible public RSS wire feeds:

| ID | Name | Category | Primary Topic |
|---|---|---|---|
| `hackernews` | **Hacker News** | Technology | Software Engineering |
| `arstechnica` | **Ars Technica** | Technology | Semiconductors & Systems |
| `krebsonsecurity` | **Krebs on Security** | Cybersecurity | Cybersecurity Threats |
| `bleepingcomputer` | **BleepingComputer** | Cybersecurity | Vulnerabilities & Exploits |
| `mitnews` | **MIT News Research** | Science | Applied Sciences |
| `nasa` | **NASA Breaking News** | Space | Space Exploration |
| `bbctech` | **BBC Technology** | World | Global Technology & Policy |
| `theverge` | **The Verge** | AI | Artificial Intelligence |

*Adding a new source is as simple as adding an entry to `DEFAULT_SOURCES` in `backend/app/services/source_registry.py`.*

---

## Data Policy & Ethics

- **Zero Aggressive Scraping**: Pulse fetches strictly from public RSS/Atom feeds at standard request intervals with polite User-Agents.
- **No Paywall or Auth Bypass**: Respects terms of service and robots.txt.
- **Attribution & Outbound Links**: Stores clean metadata, titles, and summaries, and directs users to original publishers for full reading.

---

## Running Locally

### 1. Prerequisites
- **Python** 3.10+
- **Node.js** v18+ and **npm**

---

### 2. Running the Backend (FastAPI)

From the project root (`c:\ARNS`):

```bash
# Install dependencies
pip install -r backend/requirements.txt

# Start FastAPI server (supports reload)
python -m uvicorn backend.app.main:app --reload --host 127.0.0.1 --port 8000
```

*(Note: Imports are resilient and work whether you run from `c:\ARNS` or `c:\ARNS\backend`)*.

- **API Documentation**: [http://127.0.0.1:8000/api/docs](http://127.0.0.1:8000/api/docs)
- **Health Check**: [http://127.0.0.1:8000/api/health](http://127.0.0.1:8000/api/health)
- **Ingestion Sources**: [http://127.0.0.1:8000/api/ingestion/sources](http://127.0.0.1:8000/api/ingestion/sources)
- **Stored News Articles**: [http://127.0.0.1:8000/api/news](http://127.0.0.1:8000/api/news)

---

### 3. Triggering News Ingestion

To trigger an ingestion cycle manually:

```powershell
Invoke-RestMethod -Uri "http://127.0.0.1:8000/api/ingestion/run" -Method Post
```

Example response:
```json
{
  "sources_checked": 8,
  "articles_seen": 166,
  "new_articles": 166,
  "duplicates": 0,
  "failed_sources": 0,
  "duration_seconds": 4.96
}
```

Running it again immediately proves deterministic deduplication:
```json
{
  "sources_checked": 8,
  "articles_seen": 166,
  "new_articles": 0,
  "duplicates": 166,
  "failed_sources": 0
}
```

---

### 4. Running the Frontend (Vite + React)

In a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

- **Dashboard**: [http://localhost:5173](http://localhost:5173)

The dashboard now automatically surfaces real ingested news from the database and includes a **"Sync Live Feeds"** button that invokes `/api/ingestion/run` and displays live toast metrics.

---

### 5. Running Automated Unit Tests

```bash
python -m pytest backend/tests/test_ingestion.py -v
```

Tests cover:
- HTML tag stripping and entity decoding
- Canonical URL query parameter cleaning
- Raw entry normalization
- Deterministic duplicate detection
- Database insertion and category/search querying
- Source network failure isolation
