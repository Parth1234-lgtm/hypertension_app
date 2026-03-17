from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from dotenv import load_dotenv
from datetime import datetime, timezone
import uuid
import os
import sys

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from db.connection import medical_records, patient_state, signals

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.7
)

# ── LOAD PATIENT CONTEXT FROM DB ─────────────────────────────────────────────
def load_patient_context(patient_id: str) -> dict:
    med = medical_records.find_one({"patient_id": patient_id}, {"_id": 0})
    state = patient_state.find_one({"patient_id": patient_id}, {"_id": 0})
    return {"medical": med, "state": state}

# ── BUILD SYSTEM PROMPT FROM PATIENT CONTEXT ─────────────────────────────────
def build_system_prompt(ctx: dict) -> str:
    med = ctx["medical"]
    state = ctx["state"]

    name = med["personal"]["name"].split()[0]  # first name only
    conditions = ", ".join(med["conditions"])
    meds = ", ".join([f"{m['name']} {m['dose']} ({m['timing']})" for m in med["medications"]])
    dietary = ", ".join(med["dietary_restrictions"])
    priority_flags = state["agent_notes"]["priority_flags"]
    agent_note = state["agent_notes"]["check_in_agent"]
    risk_label = state["risk_score"]["label"]

    # build schedule summary
    schedule = state["schedule"]
    med_tasks = ", ".join([m["task_id"] for m in schedule["meds"]])
    exercise_tasks = ", ".join([e["task_id"] for e in schedule["exercise"]])

    # high priority trigger list
    high_priority_flags = ["bp_above_target", "night_med_adherence_critical", "chest_pain", "severe_dizziness"]
    is_high_priority = any(f in priority_flags for f in high_priority_flags)

    prompt = f"""You are a friendly health companion for {name}, a {med['personal']['age']}-year-old patient managing {conditions}.

PATIENT CONTEXT:
- Medications: {meds}
- Dietary restrictions: {dietary}
- Current risk level: {risk_label}
- Agent notes from last cycle: {agent_note}
- Priority flags: {", ".join(priority_flags)}
- Today's med tasks: {med_tasks}
- Today's exercise tasks: {exercise_tasks}

YOUR PERSONALITY AND RULES:
- Be casual, warm and friendly like a knowledgeable friend — not a doctor or a robot
- Use {name}'s first name naturally but not in every message
- Do NOT give unsolicited advice or motivation — only respond to what the patient actually says
- Do NOT lecture about missed meds or exercise unless they bring it up or it is critical
- If patient mentions a missed task, acknowledge it simply and move on — do not repeat it
- Only escalate tone if patient reports: chest pain, severe dizziness, BP above 160/100, or difficulty breathing
- If high priority situation detected, clearly say "This sounds serious, please contact your doctor or go to A&E immediately" and set a flag
- Keep responses SHORT — 1-3 sentences max unless patient asks a detailed question
- You know their schedule so if they ask "what should I eat for lunch" you can answer from their food plan
- NEVER make up medical information — if unsure, say "check with your doctor on that one"

{"⚠️ NOTE: This patient currently has high priority flags. Stay attentive but do not alarm unnecessarily." if is_high_priority else ""}
"""
    return prompt

# ── APPEND SIGNAL TO DB ───────────────────────────────────────────────────────
def append_signal(patient_id: str, role: str, message: str):
    signals.insert_one({
        "signal_id": str(uuid.uuid4()),
        "patient_id": patient_id,
        "timestamp": datetime.now(timezone.utc),
        "type": "chat",
        "data": {
            "role": role,
            "message": message,
            "agent": "check_in_agent"
        }
    })

# ── UPDATE PATIENT STATE AFTER CHECKIN ───────────────────────────────────────
def update_checkin_summary(patient_id: str, mood: str, last_message: str, flags: list):
    update = {
        "checkin_signals_summary.last_checkin_at": datetime.now(timezone.utc),
        "checkin_signals_summary.mood": mood,
        "checkin_signals_summary.last_user_message": last_message,
    }
    # merge any new flags into priority_flags
    if flags:
        state = patient_state.find_one({"patient_id": patient_id})
        existing_flags = state["agent_notes"]["priority_flags"]
        merged = list(set(existing_flags + flags))
        update["agent_notes.priority_flags"] = merged

    patient_state.update_one(
        {"patient_id": patient_id},
        {"$set": update}
    )

# ── SIMPLE MOOD DETECTOR ──────────────────────────────────────────────────────
def detect_mood(message: str) -> str:
    msg = message.lower()
    if any(w in msg for w in ["good", "great", "fine", "well", "better", "okay"]):
        return "good"
    elif any(w in msg for w in ["tired", "stressed", "dizzy", "pain", "bad", "worse", "missed"]):
        return "bad"
    return "okay"

# ── DETECT HIGH PRIORITY FLAGS FROM USER MESSAGE ──────────────────────────────
def detect_priority_flags(message: str) -> list:
    msg = message.lower()
    flags = []
    if any(w in msg for w in ["chest pain", "chest tightness", "heart"]):
        flags.append("chest_pain_reported")
    if any(w in msg for w in ["dizzy", "dizziness", "faint", "fainted"]):
        flags.append("dizziness_reported")
    if any(w in msg for w in ["160", "170", "180", "190"]):
        flags.append("very_high_bp_reported")
    return flags

# ── MAIN CHAT LOOP ────────────────────────────────────────────────────────────
def run_checkin_agent(patient_id: str):
    ctx = load_patient_context(patient_id)
    if not ctx["medical"] or not ctx["state"]:
        print(f"❌ Patient {patient_id} not found in DB")
        return

    system_prompt = build_system_prompt(ctx)
    name = ctx["medical"]["personal"]["name"].split()[0]

    print(f"\n💬 Check-in Agent started for {name}")
    print("─" * 50)
    print("Type 'quit' to end the conversation\n")

    # opening message from agent
    opening = f"Hey {name}! How are you doing today? 😊"
    print(f"Agent: {opening}\n")
    append_signal(patient_id, "agent", opening)

    chat_history = [SystemMessage(content=system_prompt)]
    last_user_message = ""
    all_flags = []

    while True:
        user_input = input("You: ").strip()
        if user_input.lower() == "quit":
            break
        if not user_input:
            continue

        last_user_message = user_input
        append_signal(patient_id, "user", user_input)

        # detect flags from user message
        new_flags = detect_priority_flags(user_input)
        all_flags.extend(new_flags)

        # add to chat history and call LLM
        chat_history.append(HumanMessage(content=user_input))
        response = llm.invoke(chat_history)
        agent_reply = response.content

        chat_history.append(AIMessage(content=agent_reply))
        append_signal(patient_id, "agent", agent_reply)

        print(f"\nAgent: {agent_reply}\n")

    # update state after conversation ends
    mood = detect_mood(last_user_message)
    update_checkin_summary(patient_id, mood, last_user_message, all_flags)
    print("\n─" * 50)
    print(f"✅ Check-in complete. Mood: {mood}. Flags: {all_flags if all_flags else 'none'}")
    print("PatientState updated in DB.")

if __name__ == "__main__":
    run_checkin_agent("p001")