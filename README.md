# 🤖 Smart Sales Agent — Multi-Agent LLM Orchestrator

A production-grade LLM orchestration system that routes natural-language queries to specialized AI agents for **sales**, **inventory risk**, and **business reporting** — backed by real Supabase data and conversation memory.

[![FastAPI](https://img.shields.io/badge/FastAPI-009688?style=flat&logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![React](https://img.shields.io/badge/React-61DAFB?style=flat&logo=react&logoColor=black)](https://react.dev/)
[![Claude](https://img.shields.io/badge/Claude-Sonnet-6C3483?style=flat)](https://anthropic.com)
[![Supabase](https://img.shields.io/badge/Supabase-3ECF8E?style=flat&logo=supabase&logoColor=white)](https://supabase.com)

---

## What it does

You type a question in natural language — the orchestrator decides which agent should answer, pulls relevant data from the database, and returns a grounded response.

| Input | Routed to | Returns |
|---|---|---|
| `"What's selling best this week?"` | `sales_agent` | Top products by revenue, with recommendations |
| `"Which products need reordering?"` | `stock_agent` | Critical items ranked by days-to-stockout |
| `"Generate a KPI summary for store X"` | `reporting_agent` | Structured report with sales + inventory metrics |

Works in **English and Spanish** — language is auto-detected per message.

---

## Architecture

```
User query (natural language)
        │
        ▼
┌───────────────────────────────┐
│         Orchestrator          │
│  1. Detect language (EN/ES)   │
│  2. Build rich context:       │
│     - Relevant products (DB)  │
│     - 7-day sales history     │
│     - Conversation memory     │
│  3. LLM routing decision      │
│     (keyword fallback if LLM  │
│      unavailable)             │
└─────────────┬─────────────────┘
              │
      ┌───────┼───────┐
      ▼       ▼       ▼
   Sales   Report  Stock
   Agent   Agent   Agent
      │       │       │
      └───────┴───────┘
              │
          Claude Sonnet
          (Anthropic API)
              │
     Grounded response + data
```

**Memory:** Supabase `messages` table stores full conversation history. Each agent receives the last 8 turns as context.

**RAG:** `rag/vector_store.py` + `rag/retriever.py` — vector retrieval for product catalog context.

**Fallback:** When the LLM is unavailable, the orchestrator falls back to keyword-based routing and executes direct DB queries to return valid (non-hallucinatory) responses.

---

## Routing Demo

```
User: "Show me which products are about to run out"

Orchestrator detects:
  - Language: EN
  - Keywords: "run out" → stock_agent
  - Context: 5 most at-risk products from DB

stock_agent responds:
  - Wireless Headphones: 2.3 days left (stock 23, avg/day 10)
  - USB-C Hub: 4.1 days left (stock 37, avg/day 9)
  - Phone Stand: 6.0 days left (stock 12, avg/day 2)
  [CRITICAL items highlighted]
```

---

## Tech Stack

| Layer | Tech |
|---|---|
| Orchestration | Python — `Orchestrator` class with LLM routing + keyword fallback |
| LLM | Claude Sonnet (`claude-sonnet-4-20250514`) via Anthropic SDK |
| Backend API | FastAPI + Uvicorn |
| Database | Supabase (PostgreSQL) — products, sales_history, messages, conversations |
| Memory | Supabase `messages` table, last 8 turns per conversation |
| RAG | Custom vector store + retriever (`rag/`) |
| Frontend | React 18 + Vite + TypeScript + TailwindCSS + shadcn/ui |
| Frontend UI | ChatBot, KPI cards, StockTable, ReportViewer, SalesOverview, StoreSelector |

---

## Project Structure

```
agents_orchestrator/
├── agents/
│   ├── orchestrator.py       — Routing logic, context building, LLM decision
│   ├── sales_agent.py        — Sales conversation + product recommendations
│   ├── reporting_agent.py    — KPI and business report generation
│   ├── stock_agent.py        — Inventory risk analysis
│   └── base.py               — BaseAgent ABC
├── api/
│   └── routes.py             — FastAPI endpoints
├── config/
│   └── settings.py           — Supabase + Anthropic clients
├── db/
│   ├── models.py             — Data models
│   ├── seed_data.py          — Test data seeder
│   └── setup.sql             — Schema
├── memory/
│   └── store.py              — Conversation history (read/write to Supabase)
├── rag/
│   ├── vector_store.py       — Embeddings store
│   └── retriever.py          — Semantic retrieval
├── frontend/                 — React/Vite dashboard
│   └── src/
│       ├── components/dashboard/  — ChatBot, KPICard, StockTable, ReportViewer
│       └── services/api.ts        — API client
└── main.py                   — Entry point
```

---

## Setup

**Prerequisites:** Python 3.11+ · Node.js 18+ · A Supabase project · An Anthropic API key

### Backend

```bash
git clone https://github.com/Repetto-A/agents_orchestrator.git
cd agents_orchestrator

pip install -r requirements.txt

cp .env.example .env   # fill in your keys
```

**`.env`**
```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
CLAUDE_API_KEY=your-anthropic-key
```

```bash
# Seed the database
python db/seed_data.py

# Start the API
python main.py
# → http://localhost:8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# → http://localhost:5173
```

---

## API

```
POST /chat
  body: { message, store_id, conversation_id? }
  → { agent, response, data, meta }
```

---

## Extending

Add a new agent in 3 steps:
1. Create `agents/my_agent.py` extending `BaseAgent`
2. Register it in `Orchestrator.__init__`
3. Add routing keywords + LLM decision cases in `Orchestrator.route()`

---

## License

MIT
