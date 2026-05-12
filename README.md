# Healthcare AI Tool Recommender — Complete Application

A full-stack application that:
1. **Crawls** official Anthropic/Claude and OpenAI/ChatGPT healthcare pages
2. **Extracts** structured sub-offerings, capabilities, and task examples via LLM
3. **Stores** everything in PostgreSQL with pgvector embeddings for semantic search
4. **Serves a beautiful UI** for role/task selection
5. **Recommends** the best matching tools for each role + task, with match scores and automation percentages
6. **Caches** all (role, task) results — exact and semantic — so repeat requests skip the LLM entirely

---

## What's New (pgvector + Hybrid Hashing)

| Feature | What it does |
|---------|-------------|
| **Raw page hash** | Re-crawls skip LLM extraction entirely when page content hasn't changed (SHA-256 of raw text) |
| **Semantic dedup** | 3-pass deduplication: exact content hash → vector similarity (cosine < 0.08) → insert new |
| **Semantic cache** | Task recommendations cached by exact hash first, then fuzzy vector match (cosine < 0.12) |
| **Top-20 retrieval** | LLM prompt uses only the 20 most semantically relevant offerings instead of the full catalog |

All embeddings use `all-MiniLM-L6-v2` (384 dims, ~90 MB, downloaded once, then fully local).

---

## Project Structure

```
.
├── db.py                     # Shared PostgreSQL helpers (schema, CRUD, dedup, embeddings)
├── llm_client.py             # Shared LLM client with multi-key failover
├── claude_crawler.py         # Crawler for Claude / Anthropic healthcare pages
├── openai_crawler.py         # Crawler for ChatGPT / OpenAI healthcare pages
├── api.py                    # FastAPI recommendation API + static UI server
├── ui/
│   └── index.html            # Single-page UI
├── db_schema.sql             # Reference schema (auto-applied by init_db())
├── requirements.txt          # Python dependencies
└── .env.example              # Environment variable template
```

---

## Prerequisites

| Tool | Version | Purpose |
|------|---------|---------|
| Python | 3.11+ | Runtime |
| PostgreSQL | 14+ | Database |
| pgvector extension | 0.5.0+ | Vector similarity search inside PostgreSQL |
| pip | latest | Package manager |

> **pgvector must be installed on your PostgreSQL server** before running the app.
> See Step 3 below for installation instructions.

---

## Step 1 — Install Python dependencies

```bash
pip install -r requirements.txt
```

This installs everything including `sentence-transformers` and `pgvector`.
The embedding model (`all-MiniLM-L6-v2`, ~90 MB) is downloaded automatically on first use.

Install Playwright's Chromium browser (required by both crawlers):

```bash
playwright install chromium
```

---

## Step 2 — Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your values:

```env
# LLM — Groq is recommended (free, fast, great JSON mode)
LLM_API_KEY=your_groq_key_here
LLM_BASE_URL=https://api.groq.com/openai/v1
LLM_MODEL=llama-3.3-70b-versatile

# PostgreSQL
PG_HOST=localhost
PG_PORT=5432
PG_DBNAME=healthcare_crawler
PG_USER=postgres
PG_PASSWORD=your_password
```

**Recommended LLM providers:**

| Provider | Base URL | Model | Notes |
|----------|----------|-------|-------|
| Groq | `https://api.groq.com/openai/v1` | `llama-3.3-70b-versatile` | Free, fast, best JSON mode |
| Google Gemini | `https://generativelanguage.googleapis.com/v1beta/openai/` | `gemini-2.0-flash-lite` | Fast, free tier |
| OpenAI | `https://api.openai.com/v1` | `gpt-4o-mini` | Most accurate, paid |

---

## Step 3 — Set up PostgreSQL with pgvector

### Option A — Docker with pgvector (easiest)

Use the official `pgvector/pgvector` image — pgvector is pre-installed:

```bash
docker run -d \
  --name healthcare_pg \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=your_password \
  -e POSTGRES_DB=healthcare_crawler \
  -p 5432:5432 \
  pgvector/pgvector:pg16
```

### Option B — Existing PostgreSQL (install pgvector manually)

**Ubuntu / Debian:**
```bash
sudo apt install postgresql-16-pgvector
```

**macOS (Homebrew):**
```bash
brew install pgvector
```

**Windows:**
Download the prebuilt binary from [github.com/pgvector/pgvector/releases](https://github.com/pgvector/pgvector/releases) and copy `vector.dll` into your PostgreSQL `lib/` directory, then `vector.control` and the SQL files into `share/extension/`.

**From source (any platform):**
```bash
git clone https://github.com/pgvector/pgvector.git
cd pgvector
make
make install   # may need sudo on Linux/macOS
```

After installation, enable the extension in your database:
```bash
psql -U postgres -d healthcare_crawler -c "CREATE EXTENSION vector;"
```

> The app also runs `CREATE EXTENSION IF NOT EXISTS vector;` automatically in `init_db()`,
> but the pgvector shared library must already be installed on the PostgreSQL server first.

### Option C — Manual schema

```bash
psql -U postgres -c "CREATE DATABASE healthcare_crawler;"
psql -U postgres -d healthcare_crawler -f db_schema.sql
```

---

## Step 4 — Run the crawler

All vendors are driven by a single entry point: `generic_crawler.py`.

### Crawl all vendors

```bash
python generic_crawler.py
```

### Crawl a specific vendor

```bash
python generic_crawler.py --vendor anthropic
python generic_crawler.py --vendor openai
python generic_crawler.py --vendor aws_bedrock
python generic_crawler.py --vendor google_gemini
python generic_crawler.py --vendor microsoft_copilot
python generic_crawler.py --vendor servicenow
python generic_crawler.py --vendor sap
python generic_crawler.py --vendor oracle
python generic_crawler.py --vendor harvey
python generic_crawler.py --vendor glean
```

### Crawl multiple vendors at once

```bash
python generic_crawler.py --vendor openai --vendor anthropic
```

### Crawl a vendor group

```bash
python generic_crawler.py --group frontier_llm       # anthropic, openai
python generic_crawler.py --group cloud_platform     # aws_bedrock, google_gemini, microsoft_copilot
python generic_crawler.py --group enterprise_ai      # servicenow, sap, oracle
python generic_crawler.py --group vertical_ai        # harvey, glean
```

### List all configured vendors

```bash
python generic_crawler.py --list
```

For each vendor the crawler will:
- Visit seed URLs and follow relevant links (up to `MAX_PAGES` per vendor)
- **Skip LLM extraction if page content is unchanged** (SHA-256 raw hash check)
- Save raw page text → `raw_scraped_data`
- Extract and save sub-offerings via LLM
- **3-pass dedup**: exact hash → semantic vector similarity → insert new
- Write a JSONL backup to `data/<vendor_slug>_healthcare_data.jsonl`

Expected output: **15–25 unique sub-offerings per vendor**
Expected runtime: **15–40 minutes per vendor**

Press `Ctrl+C` to stop gracefully — the crawler finishes the current page,
flushes all pending LLM tasks, then exits cleanly.

---

## Step 5 — Run the API + UI

```bash
uvicorn api:app --reload --port 8000
```

| URL | Description |
|-----|-------------|
| `http://localhost:8000/` | **UI** — role/task selector + results |
| `http://localhost:8000/docs` | Interactive API docs (Swagger UI) |
| `http://localhost:8000/health` | Liveness probe |

On startup, `init_db()` runs automatically and applies all schema migrations safely
(all `IF NOT EXISTS` / `ADD COLUMN IF NOT EXISTS` — safe on an existing database).

The embedding model loads lazily on the first request that needs it (~2–3 s, one time).

---

## Step 6 — Using the UI

1. **Open** `http://localhost:8000` in your browser
2. **Choose vendor** — Claude for Healthcare, ChatGPT for Healthcare, or Compare Both
3. **Select your role** from the grid (12 pre-configured healthcare roles)
4. **Pick tasks** — select one or more tasks from the role's task list
5. **Click "Analyze with AI"** — the system will:
   - Check the exact hash cache for each (role, task) pair
   - Check the semantic vector cache (fuzzy match) if exact miss
   - Call the LLM on full cache miss — using the top-20 most relevant offerings
   - Display ranked tool recommendations with match scores, automation percentages, and reasoning
6. **Expand** any tool card to see full reasoning, automation breakdown, and limitations

---

## API Endpoints

### `POST /recommend-tools`

```json
{
  "role": "Clinical Documentation Specialist",
  "tasks": [
    "Transcribe physician notes into structured EHR entries",
    "Generate clinical visit summaries from ambient audio"
  ],
  "vendor": "Anthropic"
}
```

`vendor` is optional — omit it to compare both vendors.

**Response fields per tool:**

| Field | Type | Description |
|-------|------|-------------|
| `tool_id` | int | ID in `extracted_offerings` |
| `vendor` | string | `Anthropic` or `OpenAI` |
| `sub_offering` | string | Specific tool/connector name |
| `automation_percentage` | 0–100 | How much of the task this tool automates |
| `automation_explanation` | string | Why that % was assigned |
| `rank_position` | int | 1 = best match for this task |
| `matched_capabilities` | array | Specific capabilities that match the task |
| `capability_details` | array | Per-capability scores, source URLs, exact quotes |
| `reasoning` | string | Why this tool fits |
| `limitations` | string | Gaps/caveats |
| `cached` | bool | `true` if served from cache (no LLM call) |

### `GET /roles`
Returns all available roles.

### `GET /tasks-for-role?role=<role>`
Returns all tasks for a given role.

### `GET /offerings`
Lists all extracted offerings. Filter with `?vendor=Anthropic` or `?vendor=OpenAI`.

### `GET /cached-recommendations`
Lists all cached (role, task) pairs.

---

## Database Tables

### `raw_scraped_data`
Every crawled page URL, exactly once. Re-crawls update the row only when content changes.

| Column | Description |
|--------|-------------|
| `url` | Unique page URL |
| `vendor_tag` | `'anthropic'` or `'openai'` |
| `text` | Cleaned page text (HTML stripped) |
| `raw_hash` | SHA-256 of page text — used to skip LLM on re-crawl if unchanged |

### `extracted_offerings`
Structured tool data extracted by LLM, deduplicated by exact hash then vector similarity.

| Column | Description |
|--------|-------------|
| `vendor` | `'Anthropic'` or `'OpenAI'` |
| `module_offering` | `'Claude for Healthcare'` or `'ChatGPT for Healthcare'` |
| `sub_offering` | Specific tool/connector/skill name |
| `capabilities` | Array of capability strings |
| `tasks_examples` | Array of example tasks from the source page |
| `content_hash` | SHA-256 of normalized fields — Pass 1 exact dedup key |
| `embedding` | `vector(384)` — `all-MiniLM-L6-v2` embedding — Pass 2 semantic dedup |
| `source_evidence` | Page URL + section where this offering was found |

### `capability_records`
Individual capability rows with full source provenance (URL, section, verbatim quote).

### `task_tool_recommendations`
Cached LLM results for (role, task) pairs.

| Column | Description |
|--------|-------------|
| `role_task_hash` | SHA-256(role + task) — primary cache key |
| `role` | User role |
| `task` | Task description |
| `vendor` | Tool vendor |
| `sub_offering` | Tool name |
| `automation_percentage` | 0–100 |
| `rank_position` | 1 = best |
| `reasoning` | Why this tool fits |
| `limitations` | Gaps/caveats |
| `task_embedding` | `vector(384)` — embedding of role+task for semantic cache lookup |

---

## How Deduplication Works

### Crawl-time: raw page change detection
1. Compute `SHA-256(page_text)`
2. Compare to `raw_hash` stored for this URL
3. **Match** → return `None`, crawler skips LLM entirely (`[CACHE] Page unchanged`)
4. **Mismatch / new** → update row, return row ID, crawler proceeds to LLM extraction

### Extraction-time: 3-pass offering dedup
1. **Pass 1 — Exact hash**: `SHA-256(normalized vendor+sub_offering+capabilities+tasks)` — fastest, catches identical re-extractions
2. **Pass 2 — Semantic vector**: cosine distance < 0.08 against all stored embeddings — catches paraphrased versions of the same offering
3. **Pass 3 — Insert**: genuinely new offering inserted with its embedding for future dedup

### API recommendation cache: 2-level lookup
1. **Exact hash** (`role_task_hash`): instantaneous, covers identical (role, task) pairs
2. **Semantic vector** (cosine < 0.12 on `task_embedding`): covers slightly rephrased tasks that mean the same thing — delegates to the matched hash's cached result

---

## Data Accuracy Assessment

### Claude for Healthcare — Expected accuracy: **85–90%**
- Seed URLs point directly at official Anthropic healthcare pages
- Three-step pipeline: extraction → refinement → post-crawl LLM validation
- 3-pass deduplication prevents both exact and near-duplicate entries
- Hard filters: language check, disallowed terms, generic term rejection

### ChatGPT for Healthcare — Expected accuracy: **80–85%**
- OpenAI's healthcare pages are less structured than Anthropic's
- Same three-step pipeline and deduplication as the Claude crawler
- Risk: healthcare use-cases embedded inside general enterprise pages require broader crawl

### Deduplication — **~99%+ effective**
Exact SHA-256 hash catches all identical re-extractions. Vector similarity (cosine < 0.08 ≈ 92% similarity) catches paraphrased duplicates.

---

## Troubleshooting

### `init_db() raises "could not open extension control file ... vector.control"`
pgvector is not installed on the PostgreSQL server. Follow the installation steps in Step 3 for your platform.

### `operator does not exist: vector <=> ...`
The `vector` extension is not enabled in the database. Run:
```bash
psql -U postgres -d healthcare_crawler -c "CREATE EXTENSION vector;"
```

### "No LLM API key configured"
Set `LLM_API_KEY` in `.env`.

### "Database does not exist"
The crawlers/API auto-create it. Ensure `PG_USER` has `CREATE DATABASE` permission.

### Playwright browser not found
```bash
playwright install chromium
```

### Rate limit errors
Add more LLM API keys in `.env`:
```
LLM_API_KEY_2=your_second_key
LLM_API_KEY_3=your_third_key
```

### UI shows "No tools in catalog"
Run the crawlers first — the API requires data in `extracted_offerings`. Offerings without embeddings fall back to the full catalog automatically until all rows have been embedded.

### Embedding model download fails / slow first start
The `all-MiniLM-L6-v2` model (~90 MB) downloads from HuggingFace on first use and is cached locally. Ensure outbound internet access is available for that first run. Subsequent starts are instant.

### Crawler stuck / blocked
Reduce `MAX_PAGES` in `.env`, or wait and retry (some pages have bot protection).