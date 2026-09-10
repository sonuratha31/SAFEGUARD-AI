# SAFEGUARD AI

**AI-Powered Mechanical Safety Compliance Advisor for Industrial Machines**

SAFEGUARD AI is a full-stack industrial safety intelligence platform that monitors machine telemetry, detects risks, verifies compliance against safety standards, and generates prioritized recommendations — all with transparent, explainable AI.

---

## Architecture

```
┌─────────────────────────────────────────────────────────┐
│                    Frontend (React)                      │
│  Overview · Machines · Risk · Compliance · Alerts       │
│  Recommendations · RAG Evidence · What-If Simulator     │
└─────────────────────┬───────────────────────────────────┘
                      │ REST API
┌─────────────────────▼───────────────────────────────────┐
│               Backend API (FastAPI)                      │
├──────────────────────────────────────────────────────────┤
│  Multi-Agent System (Safety Orchestrator)                │
│  ┌─────────────┐ ┌──────────────┐ ┌───────────────────┐│
│  │ SafetyData  │ │ RiskDetection│ │  Compliance       ││
│  │ Agent (RAG) │ │ Agent        │ │  Agent            ││
│  └─────────────┘ └──────────────┘ └───────────────────┘│
│  ┌─────────────────────────────────────────────────────┐│
│  │            Recommendation Agent                     ││
│  └─────────────────────────────────────────────────────┘│
├──────────────────────────────────────────────────────────┤
│  Risk Engine  │  Compliance Engine  │  RAG Pipeline      │
│  Anomaly Det. │  Trend Analysis     │  Safety Docs       │
├──────────────────────────────────────────────────────────┤
│  Simulation Engine (5 realistic machine simulators)      │
├──────────────────────────────────────────────────────────┤
│  SQLite / PostgreSQL  │  ChromaDB (Vector Store)         │
└──────────────────────────────────────────────────────────┘
```

---

## Features

### Core Safety Capabilities
- **Risk Engine** — deterministic 0–100 risk score with full factor breakdown
- **Anomaly Detection** — Z-score + Isolation Forest on streaming telemetry
- **Trend Analysis** — linear regression prediction of degrading conditions
- **Compliance Engine** — 7 checks per machine against ISO/OSHA/NFPA standards
- **Recommendation Engine** — prioritized corrective + preventive actions

### Multi-Agent System
| Agent | Responsibility |
|-------|----------------|
| `SafetyDataAgent` | Retrieves safety evidence via RAG (supports IBM Langflow) |
| `RiskDetectionAgent` | Scores risk, detects anomalies, computes trends |
| `ComplianceAgent` | Verifies machine against standard requirements |
| `RecommendationAgent` | Generates prioritized safety actions |

### What-If Simulator
Interactively adjust temperature, vibration, RPM, pressure, load, guard status, etc. and instantly see recalculated risk score, risk level, compliance status, and affected requirements — using the **same real engine**, not AI guesswork.

### RAG Knowledge Base
Documents indexed: ISO 13849-1, ISO 13857, ISO 10816-3, ISO 4413/4414, OSHA 1910.212, OSHA 1910.217, NFPA 79, IEC 60079-14, CEMA Guidelines.

### Simulated Machines
| ID | Machine | Scenario |
|----|---------|----------|
| M-001 | CNC Machining Center | Normal |
| M-002 | Hydraulic Press | Degrading (maintenance overdue) |
| M-003 | Industrial Motor Drive | Anomaly |
| M-004 | Air Compressor Unit | Normal |
| M-005 | Conveyor Belt System | Degrading (maintenance overdue) |

---

## Project Structure

```
SAFEGUARD-AI/
├── backend/
│   ├── api/main.py          # FastAPI app (27 endpoints)
│   ├── agents/orchestrator.py  # Multi-agent safety orchestrator
│   ├── rag/
│   │   ├── pipeline.py      # RAG pipeline (ChromaDB + sentence-transformers)
│   │   └── safety_documents.py  # Embedded safety knowledge base
│   ├── risk_engine/
│   │   ├── engine.py        # Deterministic risk scorer
│   │   ├── anomaly_detection.py  # Z-score + Isolation Forest
│   │   └── trend_analysis.py    # Linear regression trend forecasting
│   ├── compliance/engine.py # ISO/OSHA/NFPA compliance checks
│   ├── recommendations/engine.py  # Prioritized recommendations
│   ├── simulation/simulator.py   # Realistic machine telemetry simulation
│   ├── telemetry/service.py # Live telemetry state management
│   ├── services/
│   │   ├── watsonx.py       # IBM WatsonX LLM integration
│   │   └── langflow.py      # IBM Langflow workflow integration
│   ├── database/
│   │   ├── models.py        # SQLAlchemy ORM models
│   │   └── connection.py    # DB session management
│   └── config.py            # Pydantic settings from .env
├── frontend/
│   └── src/
│       ├── App.tsx          # Main layout + routing
│       ├── pages/           # 8 dashboard pages
│       ├── components/ui.tsx # Shared UI components
│       └── utils/api.ts     # Type-safe API client
├── tests/
│   ├── test_risk_engine.py  # 9 risk tests
│   ├── test_simulation.py   # 8 simulation tests
│   ├── test_compliance.py   # 7 compliance tests
│   └── test_rag.py          # RAG pipeline tests
├── scripts/
├── langflow/
├── docs/
├── run_backend.py           # Backend startup script
├── .env.example             # Environment variable template
└── README.md
```

---

## Setup

### Prerequisites
- Python 3.11+
- Node.js 18+

### Backend Setup

```bash
# 1. Clone and enter the project
cd SAFEGUARD-AI

# 2. Create .env from template
cp .env.example .env
# Edit .env with your IBM credentials (optional — works without them)

# 3. Install Python dependencies
pip install -r backend/requirements.txt

# 4. Start the backend
python run_backend.py
```

The backend will start on http://localhost:8000 with:
- Interactive API docs: http://localhost:8000/docs
- Health check: http://localhost:8000/health

### Frontend Setup

```bash
cd frontend
npm install
npm run dev
```

The frontend will start on http://localhost:5173

---

## Environment Variables

Copy `.env.example` to `.env` and configure:

| Variable | Required | Description |
|----------|----------|-------------|
| `DATABASE_URL` | No | SQLite by default |
| `IBM_WATSONX_API_KEY` | For IBM AI | WatsonX API key |
| `IBM_WATSONX_PROJECT_ID` | For IBM AI | WatsonX project ID |
| `IBM_WATSONX_URL` | For IBM AI | WatsonX endpoint URL |
| `IBM_LLM_MODEL_ID` | No | Default: granite-13b-instruct-v2 |
| `IBM_EMBEDDING_MODEL_ID` | No | Default: slate-125m-english-rtrvr |
| `LANGFLOW_BASE_URL` | For Langflow | http://localhost:7860 |
| `LANGFLOW_API_KEY` | For Langflow | Langflow API key |
| `LANGFLOW_FLOW_ID_RAG` | For Langflow | RAG flow ID |
| `LANGFLOW_FLOW_ID_AGENT` | For Langflow | Agent flow ID |
| `SIMULATION_ENABLED` | No | true (default) |

---

## IBM Integration

### IBM WatsonX (LLM + Embeddings)

1. Create an IBM Cloud account at https://cloud.ibm.com
2. Provision a Watson Machine Learning (WatsonX) instance
3. Create a project and obtain your API key + project ID
4. Set `IBM_WATSONX_API_KEY` and `IBM_WATSONX_PROJECT_ID` in `.env`
5. Install: `pip install ibm-watsonx-ai`

**Without IBM WatsonX:** The system uses sentence-transformers (local) for embeddings and rule-based text for summaries.

### IBM Langflow

1. Install: `pip install langflow`
2. Start: `langflow run`
3. Import flow templates from `/langflow/` directory
4. Set `LANGFLOW_BASE_URL`, `LANGFLOW_FLOW_ID_RAG`, and `LANGFLOW_FLOW_ID_AGENT` in `.env`

**Without Langflow:** The system uses its built-in RAG pipeline directly.

### IBM Watson Orchestrate

IBM Watson Orchestrate provides enterprise agent orchestration. The `SafetyOrchestrator` class in `backend/agents/orchestrator.py` is designed to be compatible with Orchestrate's agent patterns.

1. Set `IBM_ORCHESTRATE_API_KEY` and `IBM_ORCHESTRATE_INSTANCE_URL` in `.env`
2. Register the agent skills from `langflow/` as Watson Orchestrate actions

---

## Risk Score Methodology

The risk score (0–100) is calculated deterministically from actual machine conditions:

| Factor | Max Contribution |
|--------|-----------------|
| Temperature above threshold | 20 pts |
| Vibration above threshold | 20 pts |
| Emergency stop active | 20 pts |
| Guard open/removed | 10 pts |
| Pressure above threshold | 15 pts |
| RPM overspeed | 10 pts |
| Overload | 10 pts |
| Interlock inactive | 5 pts |
| Maintenance overdue | 10 pts |
| Door unlocked | 5 pts |

Score bands: LOW (0-20) | MODERATE (21-40) | ELEVATED (41-60) | HIGH (61-80) | CRITICAL (81-100)

**The risk score is NEVER randomly generated by an LLM.**

---

## Running Tests

```bash
# Risk engine tests (fast)
python -m pytest tests/test_risk_engine.py -v

# Simulation tests (fast)
python -m pytest tests/test_simulation.py -v

# Compliance tests (requires mock)
python -m pytest tests/test_compliance.py -v

# RAG tests (slow — downloads embedding model on first run)
python -m pytest tests/test_rag.py -v
```

---

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Backend health + IBM status |
| GET | `/api/v1/facility/summary` | Facility safety overview |
| GET | `/api/v1/machines/current` | Live telemetry all machines |
| GET | `/api/v1/machines/{id}/analysis` | Full multi-agent analysis |
| GET | `/api/v1/risk/overview` | Risk scores all machines |
| GET | `/api/v1/compliance/{id}` | Compliance report |
| GET | `/api/v1/recommendations/{id}` | Recommendations |
| GET | `/api/v1/alerts` | Active alerts |
| POST | `/api/v1/rag/query` | Query safety knowledge base |
| POST | `/api/v1/whatif/simulate` | What-If simulation |
| POST | `/api/v1/simulation/scenario` | Force scenario |

Full API docs available at http://localhost:8000/docs

---

## What IBM Configuration Is Still Required

| Service | Configuration Needed | Impact if Not Configured |
|---------|---------------------|--------------------------|
| IBM WatsonX LLM | `IBM_WATSONX_API_KEY`, `IBM_WATSONX_PROJECT_ID` | Risk summaries use rule-based fallback |
| IBM WatsonX Embeddings | Same as above | RAG uses sentence-transformers locally |
| IBM Langflow | `LANGFLOW_BASE_URL`, `LANGFLOW_FLOW_ID_*` | RAG uses built-in pipeline directly |
| IBM Watson Orchestrate | `IBM_ORCHESTRATE_API_KEY` | Agents use local orchestration |

**The application is fully functional without IBM credentials.** All AI features degrade gracefully to deterministic/local implementations.

---

## License

SAFEGUARD AI — Prototype for industrial safety intelligence demonstration.
