from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import sys, os, uuid, threading
from datetime import datetime, timezone
from apscheduler.schedulers.background import BackgroundScheduler

sys.path.append(os.path.dirname(__file__))
from db.connection import medical_records, patient_state, signals, test_connection
from agents.checkin_agent import load_patient_context, build_system_prompt, append_signal, update_checkin_summary, detect_mood, detect_priority_flags
from summary.summary_agent import run_summary_agent
from ml.risk_model import predict_risk

from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv

load_dotenv()

app = FastAPI(title="Hypertension Care API")

# Fail fast (and loudly) if DB is unreachable at startup.
@app.on_event("startup")
def _startup_db_check():
    try:
        test_connection()
    except Exception:
        # Keep the API process alive for local dev UI, but routes will still error clearly.
        print("⚠️ MongoDB is not reachable at startup. Requests needing DB may return 503.")

# ── CORS — allow React frontend ───────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7
)

# in-memory chat history per patient (resets on server restart, fine for demo)
chat_histories: dict = {}

# ── REQUEST MODELS ────────────────────────────────────────────────────────────
class ChatRequest(BaseModel):
    patient_id: str
    message: str

class ScheduleStatusRequest(BaseModel):
    patient_id: str
    task_id: str
    task_type: str   # meds / food / exercise
    status: str      # done / missed
    cycle_id: Optional[int] = 1

class RunCycleRequest(BaseModel):
    patient_id: str

# ── HEALTH CHECK ──────────────────────────────────────────────────────────────
@app.get("/")
def root():
    return {"status": "ok", "message": "Hypertension Care API running"}

# ── PATIENT DATA ──────────────────────────────────────────────────────────────
@app.get("/patient/{patient_id}")
def get_patient(patient_id: str):
    """Get full patient context for frontend"""
    try:
        med = medical_records.find_one({"patient_id": patient_id}, {"_id": 0})
        state = patient_state.find_one({"patient_id": patient_id}, {"_id": 0})
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"Database unavailable: {e}")

    if not med or not state:
        raise HTTPException(status_code=404, detail="Patient not found")

    return {
        "patient_id": patient_id,
        "name": med["personal"]["name"],
        "age": med["personal"]["age"],
        "conditions": med["conditions"],
        "schedule": state.get("schedule", {}),
        "habits": state.get("habits", {}),
        "risk_score": state.get("risk_score", {}),
        "avatar_state": state.get("avatar_state", {
            "mood": "okay",
            "message": "Stay consistent 🙂",
            "color": "#eab308"
        }),
        "priority_flags": state.get("agent_notes", {}).get("priority_flags", []),
        "latest_clinical_summary": state.get("latest_clinical_summary", ""),
        "current_cycle_id": state.get("current_cycle_id", 1)
    }

# ── CHAT WITH CHECK-IN AGENT ──────────────────────────────────────────────────
@app.post("/chat")
def chat(req: ChatRequest):
    """Send message to check-in agent, get response"""
    ctx = load_patient_context(req.patient_id)
    if not ctx["medical"] or not ctx["state"]:
        raise HTTPException(status_code=404, detail="Patient not found")

    # init chat history if first message
    if req.patient_id not in chat_histories:
        system_prompt = build_system_prompt(ctx)
        chat_histories[req.patient_id] = [SystemMessage(content=system_prompt)]

    history = chat_histories[req.patient_id]

    # save user signal to DB
    append_signal(req.patient_id, "user", req.message)

    # detect flags
    new_flags = detect_priority_flags(req.message)

    # call LLM
    history.append(HumanMessage(content=req.message))
    response = llm.invoke(history)
    agent_reply = response.content
    history.append(AIMessage(content=agent_reply))

    # save agent reply signal
    append_signal(req.patient_id, "agent", agent_reply)

    # update checkin summary
    mood = detect_mood(req.message)
    update_checkin_summary(req.patient_id, mood, req.message, new_flags)

    return {
        "reply": agent_reply,
        "mood": mood,
        "flags": new_flags
    }

# ── SCHEDULE STATUS (done/missed from table) ─────────────────────────────────
@app.post("/schedule/status")
def update_schedule_status(req: ScheduleStatusRequest):
    """Record when patient marks a task done or missed"""
    signals.insert_one({
        "signal_id": str(uuid.uuid4()),
        "patient_id": req.patient_id,
        "timestamp": datetime.now(timezone.utc),
        "type": "schedule_status",
        "data": {
            "task_id": req.task_id,
            "task_type": req.task_type,
            "status": req.status,
            "cycle_id": req.cycle_id
        }
    })

    # update task status in patient_state schedule
    state = patient_state.find_one({"patient_id": req.patient_id}, {"_id": 0})
    if state:
        schedule = state.get("schedule", {})
        for category in ["meds", "food", "exercise"]:
            for task in schedule.get(category, []):
                if task.get("task_id") == req.task_id:
                    task["status"] = req.status

        patient_state.update_one(
            {"patient_id": req.patient_id},
            {"$set": {"schedule": schedule}}
        )

    # recompute habits immediately so ML model has fresh data
    recompute_habits(req.patient_id)
    return {"success": True, "task_id": req.task_id, "status": req.status}

# ── GET NOTIFICATIONS ─────────────────────────────────────────────────────────
@app.get("/notifications/{patient_id}")
def get_notifications(patient_id: str):
    """Get today's pending tasks as notifications"""
    state = patient_state.find_one({"patient_id": patient_id}, {"_id": 0})
    if not state:
        raise HTTPException(status_code=404, detail="Patient not found")

    schedule = state.get("schedule", {})
    notifications = []

    for med in schedule.get("meds", []):
        if med.get("status", "pending") == "pending":
            notifications.append({
                "id": med["task_id"],
                "type": "meds",
                "message": f"💊 Time for {med['name']} at {med['timing']}",
                "timing": med["timing"],
                "priority": med.get("priority", "normal")
            })

    for exercise in schedule.get("exercise", []):
        if exercise.get("status", "pending") == "pending":
            notifications.append({
                "id": exercise["task_id"],
                "type": "exercise",
                "message": f"🏃 {exercise['type']} — {exercise['duration_mins']} mins ({exercise['timing']})",
                "timing": exercise["timing"],
                "priority": exercise.get("priority", "normal")
            })

    for food in schedule.get("food", []):
        if food.get("status", "pending") == "pending":
            options_str = " or ".join(food["options"][:2])
            notifications.append({
                "id": food["task_id"],
                "type": "food",
                "message": f"🥗 {food['meal'].capitalize()}: Try {options_str}",
                "timing": food["meal"],
                "priority": "normal"
            })

    return {"notifications": notifications}

# ── BACKGROUND CYCLE RUNNER ──────────────────────────────────────────────────
def run_full_cycle_background(patient_id: str):
    """
    LLM-free core cycle — runs every 2 mins via scheduler.
    1. Recompute habits from signals
    2. ML risk scoring
    3. Rule-based avatar update
    Plan Agent (LLM) runs separately only when Groq tokens available.
    """
    try:
        print(f"\n[Background] Starting cycle for {patient_id}")

        # 1. recompute habits from signals (pure Python, no LLM)
        recompute_habits(patient_id)

        # 2. ML risk scoring (sklearn, no LLM)
        risk_result = predict_risk(patient_id)

        # 3. rule-based avatar update (no LLM)
        from summary.summary_agent import determine_avatar_state
        state = patient_state.find_one({"patient_id": patient_id}, {"_id": 0})
        if state:
            habits = state.get("habits", {})
            flags = state.get("agent_notes", {}).get("priority_flags", [])
            risk = state.get("risk_score", {})
            avatar = determine_avatar_state(
                risk_score=risk.get("value", 0.5),
                med_adherence=habits.get("med_adherence_rate", 0.5),
                flags=flags
            )
            patient_state.update_one(
                {"patient_id": patient_id},
                {"$set": {"avatar_state": avatar, "last_updated": datetime.now(timezone.utc)}}
            )

        # 4. try Plan Agent (needs Groq — skip if rate limited)
        try:
            from agents.plan_agent import run_plan_agent
            run_plan_agent(patient_id)
            print("[Background] Plan Agent ran successfully")
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                print("[Background] Plan Agent skipped (Groq rate limit)")
            else:
                print(f"[Background] Plan Agent failed: {e}")

        # 5. try Summary Agent (needs Groq — skip if rate limited)
        try:
            run_summary_agent(patient_id)
            print("[Background] Summary Agent ran successfully")
        except Exception as e:
            if "rate_limit" in str(e).lower() or "429" in str(e):
                print("[Background] Summary Agent skipped (Groq rate limit)")
            else:
                print(f"[Background] Summary Agent failed: {e}")

        print(f"[Background] Core cycle complete for {patient_id}")
    except Exception as e:
        print(f"[Background] Cycle failed for {patient_id}: {e}")

def run_all_patients_cycle():
    """Scheduled job — runs cycle for ALL patients (demo interval)"""
    all_patients = list(patient_state.find({}, {"patient_id": 1, "_id": 0}))
    print(f"\nScheduler: running cycle for {len(all_patients)} patients")
    for p in all_patients:
        t = threading.Thread(target=run_full_cycle_background, args=(p["patient_id"],))
        t.daemon = True
        t.start()

# start scheduler on app startup
scheduler = BackgroundScheduler()
demo_minutes = int(os.getenv("DEMO_CYCLE_MINUTES", "1"))
scheduler.add_job(run_all_patients_cycle, "interval", minutes=demo_minutes, id="demo_cycle")
scheduler.start()
print(f"Background scheduler started — demo cycle runs every {demo_minutes} min(s)")

# ── RUN FULL AGENT CYCLE ──────────────────────────────────────────────────────
@app.post("/run-cycle")
def run_cycle(req: RunCycleRequest, background_tasks: BackgroundTasks):
    """
    Triggers cycle in background — returns immediately.
    Frontend refreshes patient data after a few seconds.
    Plan Agent runs async so patient never waits.
    """
    background_tasks.add_task(run_full_cycle_background, req.patient_id)
    return {
        "success": True,
        "message": "Cycle started in background. Refresh in ~30 seconds to see updated results.",
        "patient_id": req.patient_id
    }

# ── MANUAL FAST REFRESH (ML + Summary only, no Plan Agent) ───────────────────
@app.post("/quick-refresh")
def quick_refresh(req: RunCycleRequest):
    """
    Fast version — only runs ML model + Summary Agent.
    No Plan Agent so returns in ~5 seconds.
    Use this for demo to show updated risk score + summary quickly.
    """
    print(f"\n⚡ Quick refresh for {req.patient_id}")
    # 1. recompute habits from signals (no LLM)
    recompute_habits(req.patient_id)
    # 2. run ML model (no LLM)
    risk_result = predict_risk(req.patient_id)
    # 3. update avatar state using rule-based logic (no LLM)
    from summary.summary_agent import determine_avatar_state
    state = patient_state.find_one({"patient_id": req.patient_id}, {"_id": 0})
    habits = state.get("habits", {})
    flags = state.get("agent_notes", {}).get("priority_flags", [])
    risk = state.get("risk_score", {})
    avatar = determine_avatar_state(
        risk_score=risk.get("value", 0.5),
        med_adherence=habits.get("med_adherence_rate", 0.5),
        flags=flags
    )
    patient_state.update_one(
        {"patient_id": req.patient_id},
        {"$set": {"avatar_state": avatar, "last_updated": datetime.now(timezone.utc)}}
    )
    print(f"Quick refresh done — risk: {risk_result.get('value')}, avatar: {avatar['mood']}")
    return {
        "success": True,
        "risk_score": risk_result.get("value"),
        "risk_label": risk_result.get("label"),
        "avatar_state": avatar["mood"],
    }

# ── CHAT HISTORY ──────────────────────────────────────────────────────────────
@app.get("/chat-history/{patient_id}")
def get_chat_history(patient_id: str):
    """Get last 20 chat messages for this patient"""
    recent = list(signals.find(
        {"patient_id": patient_id, "type": "chat"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(20))

    # reverse to chronological order
    recent.reverse()
    return {"messages": [
        {
            "role": msg["data"]["role"],
            "message": msg["data"]["message"],
            "timestamp": msg["timestamp"].isoformat() if hasattr(msg["timestamp"], "isoformat") else str(msg["timestamp"])
        }
        for msg in recent
    ]}

# ── TASK STATUSES (for frontend persistence) ──────────────────────────────────
@app.get("/task-statuses/{patient_id}")
def get_task_statuses(patient_id: str):
    """Get latest status for each task from signals collection"""
    recent = list(signals.find(
        {"patient_id": patient_id, "type": "schedule_status"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(100))

    # latest status per task_id
    statuses = {}
    for s in recent:
        tid = s["data"]["task_id"]
        if tid not in statuses:
            statuses[tid] = s["data"]["status"]

    return {"statuses": statuses}

# ── RECOMPUTE HABITS FROM SIGNALS ─────────────────────────────────────────────
def recompute_habits(patient_id: str):
    """Recompute habit metrics directly from signals — fast, no LLM needed"""
    recent = list(signals.find(
        {"patient_id": patient_id, "type": "schedule_status"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(50))

    if not recent:
        return

    by_type = {"meds": [], "exercise": [], "food": []}
    for s in recent:
        t = s["data"].get("task_type")
        if t in by_type:
            by_type[t].append(1 if s["data"]["status"] == "done" else 0)

    med_adherence = round(sum(by_type["meds"]) / len(by_type["meds"]), 2) if by_type["meds"] else 0.5
    exercise_adherence = round(sum(by_type["exercise"]) / len(by_type["exercise"]), 2) if by_type["exercise"] else 0.5
    diet_adherence = round(sum(by_type["food"]) / len(by_type["food"]), 2) if by_type["food"] else 0.5

    streak = 0
    for s in by_type["exercise"]:
        if s == 1: streak += 1
        else: break

    patient_state.update_one(
        {"patient_id": patient_id},
        {"$set": {
            "habits.med_adherence_rate": med_adherence,
            "habits.exercise_streak_days": streak,
            "habits.diet_adherence_rate": diet_adherence,
            "last_updated": datetime.now(timezone.utc)
        }}
    )
    print(f"Habits recomputed — med: {med_adherence}, exercise: {exercise_adherence}, diet: {diet_adherence}")