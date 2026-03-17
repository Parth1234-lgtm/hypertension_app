import os
import sys
import json
from datetime import datetime, timezone
from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from db.connection import medical_records, patient_state, signals

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.3
)

# ── AVATAR STATES ─────────────────────────────────────────────────────────────
# maps risk + adherence to an avatar mood the frontend will display
AVATAR_STATES = {
    "great":   {"mood": "great",   "gif": "great.gif",   "message": "You're doing amazing! Keep it up 💪", "color": "#22c55e"},
    "good":    {"mood": "good",    "gif": "good.gif",    "message": "Good progress! Stay consistent 😊",   "color": "#84cc16"},
    "okay":    {"mood": "okay",    "gif": "okay.gif",    "message": "Doing okay, small improvements help 🙂", "color": "#eab308"},
    "warning": {"mood": "warning", "gif": "warning.gif", "message": "Let's pay more attention this week ⚠️",  "color": "#f97316"},
    "alert":   {"mood": "alert",   "gif": "alert.gif",   "message": "Please contact your doctor soon 🚨",   "color": "#ef4444"},
}

def determine_avatar_state(risk_score: float, med_adherence: float, flags: list) -> dict:
    """Determine avatar mood based on risk score and adherence"""
    if "chest_pain_reported" in flags or "very_high_bp_reported" in flags:
        return AVATAR_STATES["alert"]
    if risk_score > 0.75 or "high_risk_escalate" in flags:
        return AVATAR_STATES["alert"]
    if risk_score > 0.60 or med_adherence < 0.4:
        return AVATAR_STATES["warning"]
    if risk_score > 0.45 or med_adherence < 0.6:
        return AVATAR_STATES["okay"]
    if risk_score > 0.30:
        return AVATAR_STATES["good"]
    return AVATAR_STATES["great"]

def load_patient_data(patient_id: str) -> dict:
    """Load all relevant data for summary generation"""
    med = medical_records.find_one({"patient_id": patient_id}, {"_id": 0})
    state = patient_state.find_one({"patient_id": patient_id}, {"_id": 0})

    # get last 20 chat signals
    recent_chats = list(signals.find(
        {"patient_id": patient_id, "type": "chat"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(20))

    # get schedule status signals
    recent_status = list(signals.find(
        {"patient_id": patient_id, "type": "schedule_status"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(30))

    return {
        "medical": med,
        "state": state,
        "recent_chats": recent_chats,
        "recent_status": recent_status
    }

def generate_clinical_summary(data: dict) -> str:
    """Use LLM to generate a concise clinical summary for the doctor"""
    med = data["medical"]
    state = data["state"]
    habits = state.get("habits", {})
    risk = state.get("risk_score", {})
    flags = state.get("agent_notes", {}).get("priority_flags", [])
    schedule = state.get("schedule", {})
    checkin = state.get("checkin_signals_summary", {})

    # compute adherence from status signals
    status_signals = data["recent_status"]
    done = sum(1 for s in status_signals if s["data"]["status"] == "done")
    total = len(status_signals)
    overall_adherence = round(done / total, 2) if total > 0 else 0

    # format recent chat highlights
    chat_highlights = []
    for c in data["recent_chats"][:5]:
        if c["data"]["role"] == "user":
            chat_highlights.append(f"Patient: {c['data']['message']}")

    system_prompt = """You are a clinical AI assistant generating a concise patient summary for a doctor.
Write in formal clinical language. Be factual and specific.
Structure your response EXACTLY as:

PATIENT SUMMARY
---------------
Patient: [name, age, conditions]
Period: [approximate timeframe]

VITAL INDICATORS
- BP: [last reading]
- Medication Adherence: [%]
- Overall Schedule Adherence: [%]
- Risk Score: [value] ([label])

KEY FINDINGS
- [finding 1]
- [finding 2]
- [finding 3]

RED FLAGS
- [flag or "None identified"]

RECOMMENDED ACTIONS
- [action 1]
- [action 2]

Keep it under 200 words. Be direct and clinical."""

    user_prompt = f"""Generate a clinical summary for:

Patient: {med['personal']['name']}, {med['personal']['age']}yo, {', '.join(med['conditions'])}
Medications: {', '.join([m['name'] + ' ' + m['dose'] for m in med['medications']])}
Last BP: {habits.get('last_bp_reading', {}).get('systolic', 'N/A')}/{habits.get('last_bp_reading', {}).get('diastolic', 'N/A')} mmHg
Med adherence rate: {habits.get('med_adherence_rate', 0)*100:.0f}%
Overall adherence: {overall_adherence*100:.0f}% ({done}/{total} tasks completed)
Risk score: {risk.get('value', 'N/A')} ({risk.get('label', 'N/A')})
Top risk factors: {risk.get('top_risk_factors', [])}
Priority flags: {flags}
Agent notes: {state.get('agent_notes', {}).get('plan_agent', 'N/A')}
Patient mood: {checkin.get('mood', 'N/A')}
Recent patient messages: {chat_highlights}"""

    response = llm.invoke([
        SystemMessage(content=system_prompt),
        HumanMessage(content=user_prompt)
    ])
    return response.content

def run_summary_agent(patient_id: str) -> dict:
    """
    Main summary agent function.
    Generates clinical summary + avatar state, saves to DB cycle_history.
    """
    print(f"\n📋 Summary Agent starting for {patient_id}")
    print("─" * 50)

    data = load_patient_data(patient_id)
    if not data["medical"] or not data["state"]:
        print(f"❌ Patient {patient_id} not found")
        return {}

    state = data["state"]
    habits = state.get("habits", {})
    risk = state.get("risk_score", {})
    flags = state.get("agent_notes", {}).get("priority_flags", [])
    cycle_id = state.get("current_cycle_id", 1)

    # generate clinical summary
    print("   Generating clinical summary...")
    clinical_summary = generate_clinical_summary(data)

    # determine avatar state
    avatar = determine_avatar_state(
        risk_score=risk.get("value", 0.5),
        med_adherence=habits.get("med_adherence_rate", 0.5),
        flags=flags
    )

    # build cycle history entry
    cycle_entry = {
        "cycle_id": cycle_id,
        "completed_at": datetime.now(timezone.utc).isoformat(),
        "risk_score": risk.get("value", 0),
        "risk_label": risk.get("label", "unknown"),
        "med_adherence_rate": habits.get("med_adherence_rate", 0),
        "diet_adherence_rate": habits.get("diet_adherence_rate", 0),
        "exercise_streak_days": habits.get("exercise_streak_days", 0),
        "priority_flags": flags,
        "clinical_summary": clinical_summary,
        "avatar_state": avatar["mood"]
    }

    # save to DB: append cycle history + update avatar state + increment cycle
    patient_state.update_one(
        {"patient_id": patient_id},
        {
            "$push": {"cycle_history": cycle_entry},
            "$set": {
                "avatar_state": avatar,
                "latest_clinical_summary": clinical_summary,
                "last_updated": datetime.now(timezone.utc)
            },
            "$inc": {"current_cycle_id": 1}
        }
    )

    print(f"✅ Summary complete")
    print(f"   Avatar state: {avatar['mood']} — {avatar['message']}")
    print(f"   Cycle {cycle_id} saved to history")
    print(f"\n{'─'*50}")
    print("CLINICAL SUMMARY:")
    print(clinical_summary)

    return {
        "clinical_summary": clinical_summary,
        "avatar_state": avatar,
        "cycle_id": cycle_id
    }

if __name__ == "__main__":
    result = run_summary_agent("p001")
