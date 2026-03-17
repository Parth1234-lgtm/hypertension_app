# 🌿 CareCompanion
### Adaptive Multi-Agent Hypertension Companion
**NUS-SYNAPXE-IMDA AI Innovation Challenge 2026 — Problem Statement 1: Agentic AI for Patient Empowerment**

---

## Overview

CareCompanion is a multi-agent Agentic AI system targeting hypertension patients in Singapore. It continuously learns from patient behaviour, adapts daily care plans, predicts cardiovascular risk via ML, and generates clinical summaries — bridging the gap between patient and clinician.

**Key capabilities:**
- Empathetic AI chatbot that adapts tone based on risk level
- Dynamic daily schedule (meds, food, exercise) that updates every 2-minute cycle
- Culturally aware food recommendations using SG FoodID (hawker/canteen, halal/veg aware)
- ML cardiovascular risk scoring (94% accuracy, GradientBoosting)
- Clinical summary generation for doctors
- 5-state avatar (🍞 bread character) reflecting patient health state

---

## System Architecture

```
Patient signals (chat + ✅/❌ schedule)
        ↓
Check-in Agent  ←→  Patient (chatbot + notifications)
        ↓
Plan Agent (LangGraph) → Food Localiser Tool + Tavily (MOH guidelines)
        ↓
ML Risk Model (sklearn) → risk score 0.0–1.0
        ↓
Summary Agent → clinical brief + avatar state
        ↓
React Frontend (chat · schedule · dashboard · avatar)
```

**MongoDB Atlas — 3 collections:**
- `medical_records` — read-only, written by doctor
- `patient_state` — agent read/write each cycle
- `signals` — append-only (chat history + schedule ✅/❌)

---

## Tech Stack

| Layer | Technology |
|-------|-----------|
| Agent framework | LangGraph + LangChain + Groq (Llama 3.3 70B) |
| Database | MongoDB Atlas |
| ML model | GradientBoosting (sklearn) — 94% accuracy |
| Backend | FastAPI + APScheduler |
| Frontend | React + Vite |
| Tools | Tavily Search + SG FoodID data |
| Training data | 2,000 synthetic hypertension patients (NHANES-inspired) |

---

## Project Structure

```
hypertension_app/
├── backend/
│   ├── main.py                      # FastAPI app + scheduler
│   ├── db/
│   │   ├── connection.py            # MongoDB connection
│   │   └── seed.py                  # Seed synthetic patient data
│   ├── agents/
│   │   ├── checkin_agent.py         # Check-in Agent (chatbot)
│   │   ├── plan_agent.py            # Plan Agent (LangGraph)
│   │   └── tools/
│   │       └── food_localiser.py    # SG food localiser tool
│   ├── ml/
│   │   └── risk_model.py            # ML risk model (train + predict)
│   └── summary/
│       └── summary_agent.py         # Summary Agent + avatar logic
├── frontend/
│   └── src/
│       ├── App.jsx
│       └── pages/
│           ├── Login.jsx
│           ├── Dashboard.jsx
│           ├── Chat.jsx
│           ├── Schedule.jsx
│           └── Summary.jsx
├── requirements.txt
└── .env.example
```

---

## Setup & Installation

### Prerequisites
- Python 3.11+
- Node.js 18+
- MongoDB Atlas account (free tier works)
- Groq API key (free at console.groq.com)
- Tavily API key (free at app.tavily.com)

### 1. Clone the repo
```bash
git clone https://github.com/yourusername/carecompanion.git
cd carecompanion
```

### 2. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your keys
```

`.env` file:
```
MONGODB_URI=mongodb+srv://username:password@cluster.mongodb.net/?appName=Cluster0
GROQ_API_KEY=gsk_...
TAVILY_API_KEY=tvly-...
DB_NAME=hypertension_app
```

### 3. Install Python dependencies
```bash
pip install -r requirements.txt
```

### 4. Seed the database
```bash
cd backend/db
python seed.py
# ✅ Seeded patient p001 — Ahmad Bin Sulaiman
```

### 5. Train the ML model
```bash
cd backend/ml
python risk_model.py
# ✅ Models saved (94% accuracy)
```

### 6. Start the backend
```bash
cd backend
uvicorn main:app --reload
# ✅ Running on http://localhost:8000
# API docs: http://localhost:8000/docs
```

### 7. Install and start the frontend
```bash
cd frontend
npm install
npm install axios
npm run dev
# ✅ Running on http://localhost:5173
```

### 8. Open the app
Go to **http://localhost:5173** and log in with patient ID: `p001`

---

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/patient/{id}` | Full patient data + avatar state |
| POST | `/chat` | Send message to check-in agent |
| POST | `/schedule/status` | Mark task ✅/❌ |
| GET | `/notifications/{id}` | Today's pending reminders |
| GET | `/chat-history/{id}` | Last 20 chat messages |
| GET | `/task-statuses/{id}` | Persisted task statuses |
| POST | `/quick-refresh` | Recompute habits + ML + avatar (LLM-free) |
| POST | `/run-cycle` | Trigger full background cycle |

---

## Demo Flow

1. **Login** — enter patient ID `p001`
2. **Dashboard** — view risk score, BP, medication adherence, priority flags
3. **Chat** — talk to the empathetic check-in agent
4. **Schedule** — mark tasks ✅ done or ❌ missed, test push notifications
5. **Summary** — view avatar state, health overview, clinical summary

---

## ML Model

The cardiovascular risk model is trained on **2,000 synthetic hypertension patients** using medically grounded distributions inspired by NHANES data.

**Features used:**
- Age, BMI, Systolic/Diastolic BP
- Medication adherence rate
- Exercise streak (days)
- Diet adherence rate
- Cholesterol (mmol/L)
- Stress level (1–7)
- Smoking status (encoded)
- Sleep hours average

**Performance:**
- Classifier accuracy: **94%**
- Regressor MAE: **0.025**
- Top risk factors: systolic BP, medication adherence, age

---

## Singapore Context

- Food recommendations use **SG FoodID (HealthHub)** data — hawker centre and canteen options
- Halal and vegetarian dietary restrictions respected
- Targets **MOH Singapore hypertension guideline**: BP < 130/80 mmHg
- Multilingual-ready architecture (`language_pref` field in patient schema)

---

## Ethics & Data Privacy

- All training data is **synthetic** (no real patient data)
- `medical_records` collection is **read-only** for all agents
- Full audit trail via `signals` collection
- Production deployment would require PDPA compliance and MOH consent framework

---

## Dataset

Training dataset included: `hypertension_risk_training_data.csv`
- 2,000 synthetic patients
- 11 clinical + behavioural features
- Risk score (0.0–1.0) + binary high-risk label

---

## References

- [MOH Singapore — Disease Burden](https://www.moh.gov.sg/resources-statistics/singapore-health-facts/disease-burden)
- [SG FoodID — HealthHub](https://www.healthhub.sg/programmes/nutrition-hub/sgfoodid)
- [NHANES Dataset](https://www.cdc.gov/nchs/nhanes/)
- [Synthea Synthetic Patient Generator](https://synthetichealth.github.io/synthea/)
- [LangGraph Documentation](https://langchain-ai.github.io/langgraph/)
- [AgentBench: Evaluating LLMs as Agents](https://arxiv.org/abs/2308.03688)

---

*Built for NUS-SYNAPXE-IMDA AI Innovation Challenge 2026 — Empower Patients. Enable Community. Elevate Healthcare.*
