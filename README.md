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

---

## Phase 8.2 Step 3: Automatic Pipeline Scheduler

Pulse features a production-grade background pipeline scheduler powered by APScheduler, executing periodic end-to-end intelligence cycles without blocking the FastAPI event loop or requiring heavyweight external infrastructure (e.g. Celery/Redis).

### 1. Architecture & Execution Model
- **Periodic Trigger**: Built on APScheduler's `BackgroundScheduler` running daemon worker threads.
- **FastAPI Lifespan**: Automatically starts when FastAPI boots up and cleanly stops when the application terminates.
- **Concurrency Protection**: On each scheduled tick, the scheduler inspects the database for active runs (`status IN ('queued', 'running')`). If an execution is in progress (whether triggered manually or by an earlier scheduled tick), the scheduled run is safely skipped and logged.
- **Full Pipeline Lifecycle**: Scheduled executions reuse the exact same `PulsePipeline` orchestration, stage transitions (`queued` $\rightarrow$ `running` $\rightarrow$ `success`/`partial_failure`/`failed`), and persistent history in `pipeline_runs` table with `trigger_type: "scheduler"`.

### 2. Configuration
Scheduler settings can be configured via `.env` or system environment variables:

| Environment Variable | Type | Default | Description |
|---|---|---|---|
| `SCHEDULER_ENABLED` | bool | `true` | Enable or disable the periodic automatic scheduler. |
| `SCHEDULER_INTERVAL_MINUTES` | int | `30` | Interval between scheduled pipeline executions in minutes. |

### 3. How to Disable Automatic Execution
To disable the scheduler (e.g. for manual-only triggering or specific CI environments):
```env
SCHEDULER_ENABLED=false
```
Or in your shell:
```bash
# Windows PowerShell
$env:SCHEDULER_ENABLED="false"
# Linux / macOS
export SCHEDULER_ENABLED=false
```
When disabled, the FastAPI lifespan will not start the scheduler, reporting `status: "disabled"`.

### 4. Inspecting Pipeline & Scheduler Status
- **Combined Pipeline & Scheduler Status**:
  ```bash
  curl http://127.0.0.1:8000/api/pipeline/status
  ```
  Returns legacy top-level pipeline run attributes along with structured `"pipeline"` and `"scheduler"` blocks:
  ```json
  {
    "status": "success",
    "run_id": "run_4b4652bd7752",
    "pipeline": {
      "status": "success",
      "run_id": "run_4b4652bd7752"
    },
    "scheduler": {
      "enabled": true,
      "status": "running",
      "running": true,
      "interval_minutes": 30,
      "next_run_time": "2026-09-13T17:45:31+00:00",
      "last_triggered_run_id": null
    }
  }
  ```

- **Dedicated Scheduler Status**:
  ```bash
  curl http://127.0.0.1:8000/api/pipeline/scheduler
  ```

- **System Health with Scheduler Metrics**:
  ```bash
  curl http://127.0.0.1:8000/api/system/health
  ```

---

## Phase 8.2 Step 4: Pipeline Operations & Observability

Pulse features a comprehensive operational management and observability suite, enabling operators to control execution lifecycle, inspect granular run histories, modify schedules dynamically at runtime, and monitor system resilience.

### 1. Operational Architecture
- **Non-blocking Control**: Start, stop, pause, and resume actions operate idempotently without killing active in-flight pipeline runs.
- **Dynamic Rescheduling**: Adjust intervals at runtime via REST API without restarting the application or creating duplicate scheduled jobs.
- **Durable Failure Tracking**: Tracks `consecutive_failure_count`, `last_failure_at`, and `last_failure_message` across restarts, auto-resetting to 0 upon any successful run.
- **Comprehensive Run Telemetry**: Every execution records per-stage metrics, overall duration, deduplication stats, and intelligence counters.

### 2. Pipeline History & Detail Endpoints

- **List Runs with Filtering**:
  ```bash
  # Filter by status (success, failed, partial_failure, running, queued)
  curl "http://127.0.0.1:8000/api/pipeline/runs?limit=20&status=success"

  # Filter by trigger type (scheduler, api, manual)
  curl "http://127.0.0.1:8000/api/pipeline/runs?trigger_type=scheduler"
  ```
  Each run contains:
  - `run_id`, `status`, `trigger_type`
  - `started_at`, `completed_at`, `duration_seconds`
  - `duplicate_articles`, `failed_ingestion_sources`
  - `stories_created`, `stories_analyzed`, `stories_importance_scored`, `stories_evolved`, `stories_relevance_scored`, `feed_items_ready`
  - `stages` breakdown and `error_message`

- **Get Specific Run Details**:
  ```bash
  curl http://127.0.0.1:8000/api/pipeline/runs/run_4b4652bd7752
  ```
  Returns 404 with descriptive detail if the `run_id` is unknown.

### 3. Scheduler Operator Controls

| Endpoint | Method | Description |
|---|---|---|
| `/api/pipeline/scheduler/start` | POST | Starts the scheduler if stopped or resumes it if paused. |
| `/api/pipeline/scheduler/stop` | POST | Stops the scheduler cleanly without aborting active runs. |
| `/api/pipeline/scheduler/pause` | POST | Pauses future ticks without aborting active runs. |
| `/api/pipeline/scheduler/resume` | POST | Resumes paused triggers or starts the scheduler. |
| `/api/pipeline/scheduler/config` | POST | Dynamically reconfigures `interval_minutes` (>= 1) and/or `enabled`. |
| `/api/pipeline/scheduler` | GET | Returns full operational status, pause state, next run time, and failure stats. |

#### Example: Runtime Interval Reconfiguration
```bash
curl -X POST http://127.0.0.1:8000/api/pipeline/scheduler/config \
  -H "Content-Type: application/json" \
  -d '{"interval_minutes": 15}'
```

### 4. Failure Tracking & Health Observability
- **`consecutive_failure_count`**: Automatically increments when a run ends in `failed` or `partial_failure`, and resets to `0` after any `success`.
- **System Health Operational Blocks**:
  `GET /api/system/health` provides operational observability across pipeline and scheduler:
  ```json
  {
    "status": "healthy",
    "pipeline": {
      "status": "success",
      "last_run_status": "success",
      "last_run_time": "2026-09-13T11:11:37.116317+00:00",
      "last_run_duration_seconds": 7.507,
      "consecutive_failure_count": 0,
      "last_failure_at": null,
      "last_failure_message": null
    },
    "scheduler": {
      "enabled": true,
      "running": true,
      "paused": false,
      "status": "running",
      "interval_minutes": 20,
      "next_run_time": "2026-09-13T17:41:42+05:30",
      "last_run_status": "success"
    }
  }
  ```


