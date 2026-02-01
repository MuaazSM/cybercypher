# 🛡️ CyberCypher - Agentic Support System

An autonomous incident response and analysis platform with real-time monitoring dashboard.

## 🏗️ Architecture

```
┌─────────────────────┐         ┌──────────────────────┐
│   Frontend          │         │   Backend            │
│   Next.js + React   │  ←───→  │   FastAPI + Python   │
│   localhost:3000    │         │   localhost:8000     │
└─────────────────────┘         └──────────────────────┘
         │                               │
         │                               │
    Dashboard UI                   Agent Workflow
    - Incidents                    - Signal Ingestion
    - Approvals                    - Anomaly Detection
    - Activity Feed                - Root Cause Analysis
                                   - Action Planning
                                   - Policy Approval
                                   - Execution
```

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Node.js 18+
- npm or yarn

### Option 1: Automated Startup (Recommended)

```bash
# One-time setup
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt

cd frontend
npm install
cd ..

# Start both services
./start.sh

# Stop services when done
./stop.sh
```

### Option 2: Manual Startup

**Terminal 1 - Backend:**
```bash
source .venv/bin/activate
python main.py
```

**Terminal 2 - Frontend:**
```bash
cd frontend
npm run dev
```

## 🌐 Access Points

- **Dashboard**: http://localhost:3000
- **API Documentation**: http://localhost:8000/docs
- **API Health**: http://localhost:8000/

## 📊 Features

### Dashboard
- ✅ Real-time incident monitoring
- ✅ Confidence scoring with evolution tracking
- ✅ Live backend status indicator
- ✅ Auto-refresh every 5 seconds
- ✅ Graceful fallback to mock data

### Approvals
- ✅ Policy-based approval workflow
- ✅ Risk assessment display
- ✅ Evidence and impact analysis
- ✅ One-click approve/reject
- ✅ Real-time status updates

### Activity Feed
- ⏳ Event log tracking (using mock data)
- ⏳ Confidence evolution display
- ⏳ Incident correlation

## 🔧 Configuration

### Backend (.env)
```bash
OPENAI_API_KEY=your_key
GROQ_API_KEY=your_key
GEMINI_API_KEY=your_key
SLACK_WEBHOOK_URL=your_webhook
GITHUB_TOKEN=your_token
GITHUB_REPO_OWNER=owner
GITHUB_REPO_NAME=repo
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## 📡 API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/` | GET | Health check |
| `/incidents` | GET | List all incidents |
| `/approvals/pending` | GET | Get pending approvals |
| `/approvals/{id}/approve` | POST | Approve an action |
| `/workflow/run` | POST | Trigger workflow execution |
| `/incidents/{id}/simulate-action` | POST | Simulate action impact |

## 🏗️ Project Structure

```
cybercypher/
├── main.py                 # FastAPI application
├── agents/                 # Agent implementations
│   ├── ingestion.py
│   ├── triage.py
│   ├── root_cause.py
│   └── action_planner.py
├── graph/                  # LangGraph workflow
├── tools/                  # LLM, KB, integrations
├── db/                     # Database models
├── frontend/               # Next.js dashboard
│   ├── src/
│   │   ├── app/           # Pages (dashboard, approvals, activity)
│   │   ├── components/    # React components
│   │   └── lib/           # API client, types, utils
│   └── public/
├── docs/                   # Documentation
├── start.sh               # Startup script
├── stop.sh                # Shutdown script
└── INTEGRATION.md         # Integration guide
```

## 🔗 Frontend-Backend Integration

The frontend connects to the backend through:

1. **API Client** (`frontend/src/lib/api.ts`)
   - Handles all backend communication
   - Transforms data between frontend/backend formats
   - Provides error handling and fallbacks

2. **Polling Hook** (`frontend/src/lib/usePolling.ts`)
   - Auto-refreshes data every 5 seconds
   - Manages loading and error states

3. **Status Indicator** (Topbar)
   - Shows live backend connection status
   - Green dot: Connected to backend
   - Red dot: Using mock data (backend offline)

See [INTEGRATION.md](./INTEGRATION.md) for detailed integration documentation.

## 🧪 Testing the Integration

### 1. Verify Backend Health
```bash
curl http://localhost:8000/
# Expected: {"status":"ok","service":"Agentic Support System"}
```

### 2. Check Incidents
```bash
curl http://localhost:8000/incidents
# Expected: {"count":0,"incidents":[]}
```

### 3. Trigger Workflow
```bash
curl -X POST http://localhost:8000/workflow/run
```

### 4. Open Dashboard
Navigate to http://localhost:3000 and verify:
- Status indicator shows green "Live"
- Incidents load (or show mock data if backend empty)
- Auto-refresh works

## 📝 Development

### Backend Development
```bash
# Run with hot reload
uvicorn main:app --reload

# Run tests
pytest

# Check database
python -m db.inspect
```

### Frontend Development
```bash
cd frontend

# Development server
npm run dev

# Build for production
npm run build

# Type checking
npm run type-check
```

## 🐛 Troubleshooting

### Backend not responding
- Check if port 8000 is available: `lsof -i :8000`
- Verify Python environment is activated
- Check `backend.log` for errors

### Frontend shows "Mock Data"
- Ensure backend is running on port 8000
- Check `.env.local` has correct API URL
- Open DevTools → Network tab to see API calls
- Verify CORS is not blocking requests

### Approval button doesn't work
- Ensure approvals exist in backend database
- Check browser console for error messages
- Verify approval ID is valid UUID format

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md)
- [Integration Guide](INTEGRATION.md)
- [Agent Pipeline](docs/ACT_PIPELINE.md)
- [Data Contracts](docs/DATA_CONTRACTS.md)
- [Frontend Setup](frontend/SETUP_GUIDE.md)

## 🔐 Security Notes

- Backend CORS is configured for all origins (development only)
- No authentication implemented yet
- Sensitive API keys should be in .env files
- .env files are gitignored by default

## 🚧 Known Limitations

- Activity feed uses mock data (backend endpoint not implemented)
- Dashboard metrics (actions today, MTTR) computed from API data
- No reject endpoint for approvals yet
- Polling instead of WebSockets for updates

## 🗺️ Roadmap

- [ ] Add activity log endpoint to backend
- [ ] Implement WebSocket for real-time updates
- [ ] Add authentication and user management
- [ ] Implement approval rejection workflow
- [ ] Add incident detail view with timeline
- [ ] Export reports and analytics
- [ ] Mobile responsive design

## 📄 License

Proprietary - CyberCypher Internal

## 👥 Team

Built by the CyberCypher team for autonomous incident response.
