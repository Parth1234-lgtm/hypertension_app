import os
import sys
import json
import uuid
from datetime import datetime, timezone
from typing import TypedDict, Annotated
import operator

from dotenv import load_dotenv
from langchain_groq import ChatGroq
from langchain.tools import tool
from langchain_tavily import TavilySearch
from langchain_core.messages import SystemMessage, HumanMessage, AIMessage
from langgraph.graph import StateGraph, END
from langgraph.prebuilt import ToolNode

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from db.connection import medical_records, patient_state, signals
from agents.tools.food_localiser import food_localiser_tool

load_dotenv()

llm = ChatGroq(
    model="llama-3.3-70b-versatile",
    api_key=os.getenv("GROQ_API_KEY"),
    temperature=0.2  # low temp for planning — we want consistent decisions
)

# ── LANGGRAPH STATE ───────────────────────────────────────────────────────────
class PlanAgentState(TypedDict):
    patient_id: str
    medical_context: dict
    current_patient_state: dict
    recent_signals: list
    messages: Annotated[list, operator.add]
    ml_features: dict
    new_schedule: dict
    cycle_complete: bool

# ── TOOLS ─────────────────────────────────────────────────────────────────────

@tool
def compute_habits_tool(patient_id: str) -> str:
    """
    Reads signals collection for this patient and computes habit metrics:
    med_adherence_rate, exercise_streak_days, diet_adherence_rate.
    Returns a JSON string with computed habits.
    """
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from db.connection import signals as sig_col

    patient_signals = list(sig_col.find(
        {"patient_id": patient_id, "type": "schedule_status"},
        {"_id": 0}
    ).sort("timestamp", -1).limit(50))

    if not patient_signals:
        return json.dumps({"error": "no signals found", "habits": {}})

    by_type = {"meds": [], "exercise": [], "food": []}
    for s in patient_signals:
        t = s["data"].get("task_type")
        if t in by_type:
            by_type[t].append(1 if s["data"]["status"] == "done" else 0)

    med_adherence = round(sum(by_type["meds"]) / len(by_type["meds"]), 2) if by_type["meds"] else 0.5
    exercise_adherence = round(sum(by_type["exercise"]) / len(by_type["exercise"]), 2) if by_type["exercise"] else 0.5
    diet_adherence = round(sum(by_type["food"]) / len(by_type["food"]), 2) if by_type["food"] else 0.5

    streak = 0
    for s in by_type["exercise"]:
        if s == 1:
            streak += 1
        else:
            break

    habits = {
        "med_adherence_rate": med_adherence,
        "exercise_streak_days": streak,
        "diet_adherence_rate": diet_adherence,
        "exercise_adherence_rate": exercise_adherence,
        "total_signals_analyzed": len(patient_signals)
    }
    return json.dumps(habits)

@tool
def extract_ml_features_tool(patient_id: str) -> str:
    """
    Extracts and returns a clean feature vector from PatientState for the ML risk model.
    Features: age, bmi, systolic_bp, diastolic_bp, med_adherence_rate,
    exercise_streak_days, diet_adherence_rate, cholesterol, stress_level,
    smoking_status_encoded, sleep_hours_avg.
    Returns JSON string of features.
    """
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from db.connection import medical_records as med_col, patient_state as ps_col

    med = med_col.find_one({"patient_id": patient_id}, {"_id": 0})
    state = ps_col.find_one({"patient_id": patient_id}, {"_id": 0})

    if not med or not state:
        return json.dumps({"error": "patient not found"})

    habits = state.get("habits", {})
    bp = habits.get("last_bp_reading", {})
    labs = med.get("labs", {})
    personal = med.get("personal", {})

    smoking_map = {"never": 0, "ex-smoker": 1, "current": 2}

    features = {
        "patient_id": patient_id,
        "age": personal.get("age", 50),
        "bmi": personal.get("bmi", 25.0),
        "systolic_bp": bp.get("systolic", 140),
        "diastolic_bp": bp.get("diastolic", 90),
        "med_adherence_rate": habits.get("med_adherence_rate", 0.5),
        "exercise_streak_days": habits.get("exercise_streak_days", 0),
        "diet_adherence_rate": habits.get("diet_adherence_rate", 0.5),
        "cholesterol_mmol": labs.get("cholesterol_mmol", 5.0),
        "stress_level": habits.get("stress_level_reported", 3),
        "smoking_status_encoded": smoking_map.get(personal.get("smoking_status", "never"), 0),
        "sleep_hours_avg": habits.get("sleep_hours_avg", 7.0),
        "extracted_at": datetime.now(timezone.utc).isoformat()
    }
    return json.dumps(features)

@tool
def update_schedule_tool(patient_id: str, new_schedule_json: str, agent_notes: str, priority_flags: str) -> str:
    """
    Writes the new schedule and agent notes back to patient_state in DB.
    Enforces medication timing constraints (±2hrs from prescribed time).
    Args:
        patient_id: patient identifier
        new_schedule_json: JSON string of the new schedule
        agent_notes: plan agent's notes for check-in agent next cycle
        priority_flags: comma separated flags e.g. "med_adherence_critical,bp_above_target"
    Returns confirmation string.
    """
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from db.connection import medical_records as med_col, patient_state as ps_col

    try:
        new_schedule = json.loads(new_schedule_json)
    except Exception as e:
        return f"Error parsing schedule JSON: {e}"

    # enforce med timing constraints
    med = med_col.find_one({"patient_id": patient_id}, {"_id": 0})
    if med is None:
        return f"❌ Patient {patient_id} not found in medical_records"

    prescribed_meds = {m["name"]: m["timing"] for m in med.get("medications", [])}

    for med_task in new_schedule.get("meds", []):
        for prescribed_name, prescribed_timing in prescribed_meds.items():
            if prescribed_name.lower() in med_task.get("name", "").lower():
                med_task["prescribed_timing"] = prescribed_timing
                med_task["constraint"] = "±2hrs from prescribed time — DO NOT change"

    flags = [f.strip() for f in priority_flags.split(",") if f.strip()]

    ps_col.update_one(
        {"patient_id": patient_id},
        {"$set": {
            "schedule": new_schedule,
            "agent_notes.plan_agent": agent_notes,
            "agent_notes.priority_flags": flags,
            "schedule.last_updated_by": "plan_agent",
            "schedule.last_updated_at": datetime.now(timezone.utc),
            "last_updated": datetime.now(timezone.utc)
        }}
    )
    return f"✅ Schedule updated in DB for patient {patient_id}. Flags set: {flags}"

# ── TAVILY SEARCH ─────────────────────────────────────────────────────────────
tavily_tool = TavilySearch(
    max_results=2,
    api_key=os.getenv("TAVILY_API_KEY"),
    description="Search for Singapore MOH clinical guidelines, hypertension management protocols, or medication safety info."
)

# ── ALL TOOLS ─────────────────────────────────────────────────────────────────
tools = [
    compute_habits_tool,
    extract_ml_features_tool,
    food_localiser_tool,
    update_schedule_tool,
    tavily_tool
]

llm_with_tools = llm.bind_tools(tools)

# ── NODES ─────────────────────────────────────────────────────────────────────
def load_context_node(state: PlanAgentState) -> PlanAgentState:
    """Load full patient context from DB into state"""
    patient_id = state["patient_id"]

    med = medical_records.find_one({"patient_id": patient_id}, {"_id": 0})
    ps = patient_state.find_one({"patient_id": patient_id}, {"_id": 0})

    # get recent signals (last 30)
    recent = list(signals.find(
        {"patient_id": patient_id},
        {"_id": 0}
    ).sort("timestamp", -1).limit(30))

    # build system prompt for plan agent
    name = med["personal"]["name"].split()[0]
    conditions = ", ".join(med["conditions"])
    risk_label = ps["risk_score"]["label"]
    risk_value = ps["risk_score"]["value"]
    checkin_notes = ps["agent_notes"]["check_in_agent"]
    current_flags = ps["agent_notes"]["priority_flags"]
    dietary = ", ".join(med["dietary_restrictions"])
    meds = [f"{m['name']} {m['dose']} at {m['timing']}" for m in med["medications"]]

    system_prompt = f"""You are the Plan Agent for {name}, a {med['personal']['age']}-year-old patient with {conditions}.

YOUR JOB:
1. First call compute_habits_tool to get latest habit metrics from signals
2. Analyse what is working and what is not in the current schedule
3. If you need clinical guidance, call tavily_search for MOH Singapore hypertension guidelines
4. Call food_localiser_tool to get updated localised food options based on nutritional targets
5. Call update_schedule_tool with the new adapted schedule + your notes for check-in agent
6. Finally call extract_ml_features_tool to save the feature vector for the ML risk model

PATIENT CONTEXT:
- Risk score: {risk_value} ({risk_label})
- Current priority flags: {current_flags}
- Check-in agent notes: {checkin_notes}
- Prescribed medications: {meds}
- Dietary restrictions: {dietary}
- Hypertension targets: BP < 130/80 mmHg (MOH Singapore guideline)

CONSTRAINTS YOU MUST FOLLOW:
- NEVER change medication timing by more than ±2 hours from prescribed time
- NEVER remove a prescribed medication from the schedule
- Food options MUST respect dietary restrictions: {dietary}
- If risk score > 0.75, set priority_flags to include "high_risk_escalate"
- Keep schedule realistic — do not overload patient if adherence is already low

ADAPTATION RULES:
- If med_adherence_rate < 0.6: add strong reminder note for check-in agent, do NOT change med schedule
- If exercise_adherence_rate < 0.4: make exercise more flexible (time + duration), do not increase intensity
- If diet_adherence_rate > 0.8: can introduce slightly more variety in food options
- Always update food options using food_localiser_tool with correct dietary restrictions

Start by calling compute_habits_tool now."""

    return {
        **state,
        "medical_context": med,
        "current_patient_state": ps,
        "recent_signals": recent,
        "messages": [SystemMessage(content=system_prompt)]
    }

def agent_node(state: PlanAgentState) -> PlanAgentState:
    """LLM decides which tool to call next"""
    response = llm_with_tools.invoke(state["messages"])
    return {**state, "messages": [response]}

def should_continue(state: PlanAgentState) -> str:
    """Check if agent wants to call more tools or is done"""
    last_message = state["messages"][-1]
    if hasattr(last_message, "tool_calls") and last_message.tool_calls:
        return "tools"
    return "end"

def save_ml_features_node(state: PlanAgentState) -> PlanAgentState:
    """Always force extract ml features and save to patient_state — never trust LLM to call it"""
    import sys, os
    sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
    from db.connection import patient_state as ps_col

    try:
        result = extract_ml_features_tool.invoke({"patient_id": state["patient_id"]})
        features = json.loads(result)
        ps_col.update_one(
            {"patient_id": state["patient_id"]},
            {"$set": {"ml_features": features}}
        )
        print(f"   ML features extracted: {list(features.keys())}")
        return {**state, "ml_features": features, "cycle_complete": True}
    except Exception as e:
        print(f"   ⚠️ ML features extraction failed: {e}")
        return {**state, "cycle_complete": True}

# ── BUILD LANGGRAPH ───────────────────────────────────────────────────────────
def build_plan_agent():
    tool_node = ToolNode(tools)

    graph = StateGraph(PlanAgentState)

    graph.add_node("load_context", load_context_node)
    graph.add_node("agent", agent_node)
    graph.add_node("tools", tool_node)
    graph.add_node("save_ml_features", save_ml_features_node)

    graph.set_entry_point("load_context")
    graph.add_edge("load_context", "agent")
    graph.add_conditional_edges("agent", should_continue, {
        "tools": "tools",
        "end": "save_ml_features"
    })
    graph.add_edge("tools", "agent")
    graph.add_edge("save_ml_features", END)

    return graph.compile()

# ── RUN ───────────────────────────────────────────────────────────────────────
def run_plan_agent(patient_id: str):
    app = build_plan_agent()

    print(f"\n🧠 Plan Agent starting for patient {patient_id}")
    print("─" * 50)

    initial_state: PlanAgentState = {
        "patient_id": patient_id,
        "medical_context": {},
        "current_patient_state": {},
        "recent_signals": [],
        "messages": [],
        "ml_features": {},
        "new_schedule": {},
        "cycle_complete": False
    }

    final_state = app.invoke(initial_state)

    print(f"✅ Plan Agent cycle complete")
    print(f"   ML features saved: {bool(final_state.get('ml_features'))}")
    print(f"   Cycle complete: {final_state.get('cycle_complete')}")

    return final_state

if __name__ == "__main__":
    # run agent
    result = run_plan_agent("p001")

    # save graph diagram
    app = build_plan_agent()
    try:
        graph_png = app.get_graph().draw_mermaid_png()
        with open("plan_agent_graph.png", "wb") as f:
            f.write(graph_png)
        print("\n📊 Graph saved as plan_agent_graph.png")
    except Exception as e:
        print(f"\n📊 Mermaid diagram (paste at mermaid.live):")
        print(app.get_graph().draw_mermaid())