# 🛡️ Stabilix - Agentic Incident Response System
## Team Name: Pied Piper (B098)
### Muaaz Shaikh, Kamakshi Bahuguna, Aditya Rajkumar

> **Autonomous incident detection, analysis, and resolution powered by multi-agent AI workflows**

Stabilix is an intelligent incident response platform that uses 10 specialized AI agents to automatically detect, analyze, and resolve production incidents. Built with LangGraph orchestration and multi-LLM reasoning, it provides end-to-end automation from signal ingestion to action execution.

---

## 🤖 The 10-Agent Architecture

Stabilix uses a **multi-agent workflow** organized into 5 distinct pipeline stages:

### 🔍 **OBSERVE Pipeline** (Agents 1-4)
Collects and clusters raw signals into actionable incidents.

**Agent 1: Signal Ingestion**
- Collects events from DataDog, Zendesk, webhooks, and logs
- Implements idempotency to avoid duplicate processing
- Normalizes timestamps and formats across sources

**Agent 2: Normalization & Enrichment**
- Converts diverse formats to standard schema
- Enriches with merchant metadata and geographic info
- Classifies error types consistently

**Agent 3: Anomaly Detection**
- Compares metrics against historical baselines
- Calculates z-scores and deviation percentages
- Detects spikes, drops, and pattern changes (98% confidence threshold)

**Agent 4: Pattern Detection & Clustering**
- Uses DBSCAN algorithm to group similar events
- Computes similarity metrics between events
- Creates incident clusters with cohesion scores

### 🧠 **REASON Pipeline** (Agents 5-6)
Analyzes incident clusters and determines root causes.

**Agent 5: Incident Triage**
- Evaluates if cluster warrants incident creation
- Assigns severity: CRITICAL, HIGH, MEDIUM, LOW
- Calculates blast radius (merchants/regions affected)
- Estimates business impact (revenue, customer trust)

**Agent 6: Root Cause Analysis**
- Generates multiple hypotheses using LLM reasoning (GPT-4, Claude, Gemini)
- Retrieves similar past incidents from RAG knowledge base (ChromaDB)
- Scores hypotheses by confidence level (0-100%)
- Ranks by probability and supporting evidence

### ⚖️ **DECIDE Pipeline** (Agents 7-8)
Plans actions and validates them against organizational policies.

**Agent 7: Action Planner**
- Generates context-aware remediation actions
- Evaluates risk levels: LOW, MEDIUM, HIGH, CRITICAL
- Calculates success probabilities from past responses
- Creates action plan with detailed rationale

**Agent 8: Policy Approval Gate**
- Validates each action against governance policies
- Checks: change control, compliance (GDPR), customer impact
- Auto-approves low-risk actions (<30% risk score)
- Routes medium/high-risk actions for manual review

### ⚡ **ACT Pipeline** (Agent 9)
Executes approved actions with external integrations.

**Agent 9: Execution Engine**
- Creates GitHub issues with full incident context
- Sends Slack notifications to team channels
- Sets up DataDog monitoring dashboards
- Generates customer communication drafts
- Implements idempotency to prevent duplicate executions
- Records all actions with external references (issue #, URLs)

### 🤝 **Merchant Response Pipeline** (Agent 11)
Communicates with affected merchants and monitors support tickets.

**Agent 11: Merchant Response & Support Ticket Monitor**
- Classifies incidents as technical vs customer-facing issues
- Generates personalized merchant communication for non-technical issues
- Sends responses via email, in-app notifications, and support ticket replies
- Monitors support tickets through resolution completion
- Tracks customer satisfaction scores
- Auto-closes resolved tickets with resolution summaries
- Logs all merchant interactions for future learning
- Escalates complex issues to human support agents

### 📚 **LEARN Pipeline** (Agent 10)
Continuously improves from outcomes.

**Agent 10: Feedback & Learning**
- Records incident outcomes and recovery metrics
- Updates RAG knowledge base with learned patterns
- Improves future response by adjusting triage rules
- Trains models on incident-response patterns
- Adjusts confidence scoring based on accuracy
- Incorporates merchant feedback into knowledge base

---

## 🏗️ Tech Stack

### **Backend (Python)**
- **FastAPI** - High-performance async web framework
- **LangGraph** - Multi-agent workflow orchestration
- **LangChain** - LLM integration and prompt engineering
- **SQLAlchemy** - ORM for PostgreSQL database
- **Pydantic** - Data validation and settings management
- **ChromaDB** - Vector database for RAG (Retrieval-Augmented Generation)
- **PostgreSQL** - Primary database for incidents, actions, approvals

### **LLM Providers**
- **OpenAI** (GPT-4, GPT-3.5-turbo) - Primary reasoning engine
- **Groq** (Llama 3, Mixtral) - Fast inference for triage
- **Google Gemini** (Gemini Pro) - Alternative reasoning

### **Frontend (TypeScript/React)**
- **Next.js 15** - React framework with App Router
- **React 19** - UI library with server components
- **TypeScript** - Type-safe development
- **Tailwind CSS** - Utility-first styling
- **shadcn/ui** - Component library (Card, Dialog, Button, Badge, Table)
- **Lucide React** - Icon library

### **External Integrations**
- **GitHub API** - Issue creation and tracking
- **Slack API** - Team notifications and alerts
- **DataDog API** - Monitoring and metrics collection
- **Zendesk API** - Customer support ticket ingestion

### **Infrastructure**
- **Docker** - Containerization (optional)
- **PostgreSQL** - Primary database
- **ChromaDB** - Vector embeddings for RAG
- **Git** - Version control

---

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- PostgreSQL (for production) or SQLite (for development)

### Installation

```bash
# Clone repository
git clone https://github.com/MuaazSM/stabilix.git
cd stabilix

# Backend setup
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# Frontend setup
cd frontend
npm install
cd ..

# Configure environment
cp .env.example .env
# Edit .env with your API keys

# Start services
./start.sh
```

### Access Points

- **Dashboard**: http://localhost:3000
- **API Docs**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/

---

## 🎯 Key Features

### 🔄 **Autonomous Incident Response**
- End-to-end automation from detection to resolution
- 5-second average response time (detection → action)
- 22-minute average resolution time (full incident lifecycle)

### 🧪 **Multi-LLM Reasoning**
- Parallel hypothesis generation across multiple models
- Confidence scoring and evidence ranking
- RAG-enhanced context from historical incidents

### 🛡️ **Policy-Based Governance**
- Automated approval for low-risk actions (<30% risk)
- Manual review for medium/high-risk changes
- Compliance validation (GDPR, SOC 2, change control)

### 📊 **Real-Time Dashboard**
- Live incident monitoring with auto-refresh
- Confidence score evolution tracking
- Backend health status indicator
- Graceful fallback to mock data

### 🔗 **External Integrations**
- GitHub issue creation with incident context
- Slack notifications to team channels
- DataDog dashboard setup and monitoring
- Customer communication drafts

---

## 📊 Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│                    OBSERVE PIPELINE                         │
│  Agent 1-4: Ingest → Normalize → Detect → Cluster          │
└─────────────────┬───────────────────────────────────────────┘
                  │ Incident Clusters
                  ↓
┌─────────────────────────────────────────────────────────────┐
│                     REASON PIPELINE                         │
│  Agent 5-6: Triage → Root Cause Analysis (LLM + RAG)       │
└─────────────────┬───────────────────────────────────────────┘
                  │ Root Cause Hypotheses (ranked by confidence)
                  ↓
┌─────────────────────────────────────────────────────────────┐
│                     DECIDE PIPELINE                         │
│  Agent 7-8: Action Planning → Policy Approval Gate         │
└─────────────────┬───────────────────────────────────────────┘
                  │ Approved Actions
                  ↓
┌─────────────────────────────────────────────────────────────┐
│                      ACT PIPELINE                           │
│  Agent 9: Execute (GitHub, Slack, DataDog)                 │
└─────────────────┬───────────────────────────────────────────┘
                  │ Executed Actions + External Refs
                  ↓
┌─────────────────────────────────────────────────────────────┐
│             MERCHANT RESPONSE PIPELINE                      │
│  Agent 11: Classify → Respond → Monitor Support Tickets    │
└─────────────────┬───────────────────────────────────────────┘
                  │ Merchant Communications & Ticket Status
                  ↓
┌─────────────────────────────────────────────────────────────┐
│                     LEARN PIPELINE                          │
│  Agent 10: Record Outcomes → Update Knowledge Base         │
└─────────────────────────────────────────────────────────────┘
```

---

## 🎬 Demo System

Stabilix includes a terminal-based demo to showcase the agent workflow:

```bash
# Run interactive demo
./demo/run.sh

# Options:
# 1) Terminal Walkthrough - Interactive, detailed architecture walkthrough
# 2) Full Simulation - Complete incident with GitHub integration  
# 3) Quick Demo - Fast version, no pauses
```

**Features:**
- Real GitHub issue creation (set `GITHUB_TOKEN` in `.env`)
- Step-by-step agent execution visualization
- LLM reasoning and confidence scoring display
- Policy approval gate simulation
- Full incident timeline with timestamps

See [demo/TECHNICAL_GUIDE.md](demo/TECHNICAL_GUIDE.md) for details.

---

## 📡 API Reference

### Core Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/incidents` | GET | List all incidents with pagination |
| `/incidents/{id}` | GET | Get incident details |
| `/approvals/pending` | GET | Get pending approval actions |
| `/approvals/{id}/approve` | POST | Approve an action |
| `/workflow/run` | POST | Trigger workflow execution |
| `/incidents/{id}/simulate-action` | POST | Simulate action impact |

Full API documentation: http://localhost:8000/docs

---

## 🔧 Configuration

### Required Environment Variables

```bash
# LLM Provider API Keys
OPENAI_API_KEY=sk-...
GROQ_API_KEY=gsk_...
GEMINI_API_KEY=AI...

# External Integrations
GITHUB_TOKEN=ghp_...
GITHUB_REPO_OWNER=YourUsername
GITHUB_REPO_NAME=stabilix
SLACK_WEBHOOK_URL=https://hooks.slack.com/...

# Database
DATABASE_URL=postgresql://user:pass@localhost:5432/stabilix

# Optional
DATADOG_API_KEY=...
DATADOG_APP_KEY=...
```

---

## 📈 Performance Metrics

- **Detection Speed**: ~3 seconds (event ingestion → incident cluster)
- **Analysis Time**: ~4 seconds (triage + root cause with LLM)
- **Decision Time**: ~3 seconds (action planning + policy validation)
- **Execution Time**: ~8 seconds (GitHub + Slack + monitoring setup)
- **Total Automation**: ~18 seconds (human approval not required for low-risk)

**Incident Resolution:**
- Average: 22 minutes (includes external system recovery)
- Auto-approved actions: 94% success rate
- Manual review time: Median 5 minutes

---

## 🧪 Testing

```bash
# Backend tests
pytest tests/

# Integration tests
pytest tests/integration/

# Agent workflow tests
pytest tests/agents/

# Frontend tests
cd frontend
npm test
```

---

## 📚 Documentation

- [Architecture Details](docs/ARCHITECTURE.md)
- [Frontend-Backend Integration](INTEGRATION.md)
- [Agent Pipeline Documentation](docs/)
  - [OBSERVE Pipeline](docs/OBSERVE_PIPELINE.md)
  - [REASON Pipeline](docs/REASON_PIPELINE.md)
  - [DECIDE Pipeline](docs/DECIDE_PIPELINE.md)
  - [ACT Pipeline](docs/ACT_PIPELINE.md)
  - [LEARN Pipeline](docs/LEARN_PIPELINE.md)
- [Data Contracts](docs/DATA_CONTRACTS.md)
- [Demo System Guide](demo/TECHNICAL_GUIDE.md)
- [GitHub Integration Setup](demo/GITHUB_SETUP.md)

---

## 🛠️ Development

### Backend Development

```bash
source .venv/bin/activate
uvicorn main:app --reload --port 8000
```

### Frontend Development

```bash
cd frontend
npm run dev
```

### Database Management

```bash
# Run migrations
alembic upgrade head

# Create migration
alembic revision --autogenerate -m "description"

# Reset database
python -m db.reset
```

---

## 🐛 Troubleshooting

### Backend Issues
- **Port 8000 in use**: `lsof -i :8000` then `kill -9 <PID>`
- **Database connection error**: Check PostgreSQL is running
- **LLM API errors**: Verify API keys in `.env`

### Frontend Issues
- **Shows "Mock Data"**: Backend not running on port 8000
- **CORS errors**: Check backend CORS settings
- **Type errors**: Run `npm run type-check`

### Demo Issues
- **GitHub issues not creating**: Set `GITHUB_TOKEN` in `.env`
- **Terminal colors broken**: Set `export TERM=xterm-256color`

---

## 📄 License

Proprietary - Stabilix Internal

---

## 👥 Contributors

Built by the Stabilix team for autonomous incident response.

**Contact**: [GitHub Issues](https://github.com/MuaazSM/stabilix/issues)

---

## 🙏 Acknowledgments

- **LangChain** for LLM orchestration framework
- **LangGraph** for multi-agent workflow graphs
- **Vercel** for Next.js and deployment platform
- **FastAPI** for high-performance API framework
