# Voice AI GEPA – Self-Healing Voice Agent (with optional Keep integration)

A modular project that combines a DSPy-based voice agent, a GEPA prompt optimizer, and a lightweight dashboard. Optionally, it integrates with Keep (AIOps) via webhooks for alerting and workflow automation.

## Features
- DSPy voice agent for dealership call handling
- GEPA optimizer API for automatic prompt improvement
- Dashboard for real-time metrics and trends
- Optional Keep integration for alerting, correlation, and incident workflows

## Prerequisites
- Python 3.11+
- Docker & Docker Compose v2+
- PostgreSQL 15+ (or use the provided Docker service)
- Optional: Keep Platform (via Docker)

## Quickstart
1) Install dependencies
```bash
pip install -r requirements.txt
```

2) Configure environment
```bash
cp .env.example .env
# Edit .env and set at minimum:
# ANTHROPIC_API_KEY, DATABASE_URL
```

3) Start core services
```bash
docker-compose up -d postgres
docker-compose up voice-agent gepa-optimizer dashboard
```

4) Verify
```bash
pytest tests/unit -q
curl http://localhost:8000/health   # GEPA optimizer
curl http://localhost:5000          # Dashboard
```

## Project Structure
```
voice-ai-keep-gepa/
├── voice_agent/           # DSPy voice AI agent modules
├── gepa_optimizer/        # GEPA optimization service (Flask API)
├── dashboard/             # Monitoring dashboard (Flask + Chart.js)
├── keep_integration/      # Keep AIOps integration layer
│   ├── workflows/         # YAML workflow definitions
│   ├── webhooks.py        # Webhook handlers for Keep communication
│   └── setup.md           # Keep configuration instructions
├── tests/                 # Unit/integration tests
├── docker/                # Docker configurations per service
├── scripts/               # Helper scripts (setup, dev, deploy)
├── .env.example           # Environment variable template
└── docker-compose.yml     # Multi-service orchestration
```

Place new modules at `<service>/<feature>.py` with tests at `tests/<service>/test_<feature>.py`.

## Common Commands
- `make setup` – install deps and init DB
- `make lint` – run ruff checks
- `make format` – format with ruff
- `make test` – full test suite with coverage
- `make test-unit` – fast unit tests
- `make test-integration` – integration tests
- `docker-compose up` – start core services
- `python gepa_optimizer/service.py` – run GEPA locally
- `python voice_agent/simulate_calls.py` – simulate calls

## Keep Integration (Optional)
1) Start Keep: `docker-compose up -d keep`
2) Open UI: http://localhost:3000
3) In UI: add webhook provider, import workflows from `keep_integration/workflows/`, and connect GEPA webhook
4) Test webhook:
```bash
curl -X POST http://localhost:8000/webhook/keep \
  -H "Content-Type: application/json" \
  -d '{"alert":"conversion_drop","rate":0.55}'
```

## Testing
- Framework: pytest + coverage
- Targets: ≥85% coverage for new code
- Run: `make test` or `pytest tests/unit -q`
