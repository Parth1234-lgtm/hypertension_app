from connection import medical_records, patient_state, signals
from datetime import datetime, timezone
import uuid

def seed_patient():
    patient_id = "p001"

    # ── 1. MEDICAL RECORDS (read only, doctor written) ──────────────────────
    med_record = {
        "patient_id": patient_id,
        "personal": {
            "name": "Ahmad Bin Sulaiman",
            "age": 54,
            "gender": "M",
            "ethnicity": "malay",
            "language_pref": "english",
            "bmi": 27.4,
            "smoking_status": "ex-smoker",
            "alcohol_units_per_week": 0
        },
        "conditions": ["hypertension", "hyperlipidaemia"],
        "medications": [
            {
                "name": "Amlodipine",
                "dose": "5mg",
                "frequency": "once daily",
                "timing": "morning",
                "flexible_window_hrs": 2
            },
            {
                "name": "Atorvastatin",
                "dose": "20mg",
                "frequency": "once daily",
                "timing": "night",
                "flexible_window_hrs": 2
            }
        ],
        "bp_baseline": {
            "systolic": 148,
            "diastolic": 94,
            "recorded_at": "2025-12-01"
        },
        "labs": {
            "cholesterol_mmol": 5.8,
            "ldl_mmol": 3.6,
            "sodium_mmol": 141,
            "potassium_mmol": 3.7,
            "hba1c_pct": 5.6
        },
        "allergies": [],
        "dietary_restrictions": ["halal"],
        "doctor_notes": "Patient has been non-adherent with evening statin. Stress at work cited. Encourage lifestyle changes alongside medication."
    }

    # ── 2. PATIENT STATE (agent read+write) ──────────────────────────────────
    pat_state = {
        "patient_id": patient_id,
        "last_updated": datetime.now(timezone.utc),
        "current_cycle_id": 1,

        "schedule": {
            "last_updated_by": "plan_agent",
            "last_updated_at": datetime.now(timezone.utc),
            "meds": [
                {
                    "task_id": "morning_amlodipine",
                    "name": "Amlodipine 5mg",
                    "timing": "08:00",
                    "flexible_window": "±2hrs",
                    "priority": "critical"
                },
                {
                    "task_id": "night_atorvastatin",
                    "name": "Atorvastatin 20mg",
                    "timing": "22:00",
                    "flexible_window": "±2hrs",
                    "priority": "critical"
                }
            ],
            "food": [
                {
                    "task_id": "breakfast",
                    "meal": "breakfast",
                    "options": ["oats with banana", "wholemeal bread with egg"],
                    "nutritional_targets": {
                        "sodium_mg_max": 400,
                        "potassium_mg_min": 300
                    }
                },
                {
                    "task_id": "lunch",
                    "meal": "lunch",
                    "options": ["yong tau foo (no added salt)", "cai png with steamed fish and veg"],
                    "nutritional_targets": {
                        "sodium_mg_max": 600,
                        "potassium_mg_min": 400
                    }
                },
                {
                    "task_id": "dinner",
                    "meal": "dinner",
                    "options": ["home cooked soup with brown rice", "ban mian no soup add"],
                    "nutritional_targets": {
                        "sodium_mg_max": 500,
                        "potassium_mg_min": 350
                    }
                }
            ],
            "exercise": [
                {
                    "task_id": "evening_walk",
                    "type": "brisk walk",
                    "duration_mins": 30,
                    "timing": "evening",
                    "flexible": True,
                    "priority": "moderate"
                }
            ]
        },

        "habits": {
            "med_adherence_rate": 0.55,
            "exercise_streak_days": 2,
            "diet_adherence_rate": 0.70,
            "sleep_hours_avg": 6.0,
            "last_bp_reading": {
                "systolic": 145,
                "diastolic": 91,
                "recorded_at": datetime.now(timezone.utc),
                "source": "user_reported"
            },
            "stress_level_reported": 4
        },

        "risk_score": {
            "value": 0.68,
            "label": "high",
            "computed_at": datetime.now(timezone.utc),
            "features_used": ["bp", "med_adherence_rate", "age", "bmi", "cholesterol", "smoking_status"]
        },

        "agent_notes": {
            "check_in_agent": "Patient misses night statin consistently. Responds well to friendly tone. Mentions work stress.",
            "plan_agent": "Prioritise med adherence over exercise changes this cycle. Food options adapted for halal.",
            "priority_flags": ["night_med_adherence_critical", "bp_above_target", "stress_elevated"]
        },

        "cycle_history": [],

        "checkin_signals_summary": {
            "last_checkin_at": datetime.now(timezone.utc),
            "mood": "okay",
            "last_user_message": "I forgot my night medicine again"
        }
    }

    # ── 3. SEED SOME INITIAL SIGNALS ─────────────────────────────────────────
    initial_signals = [
        {
            "signal_id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "timestamp": datetime.now(timezone.utc),
            "type": "chat",
            "data": {
                "role": "user",
                "message": "I forgot my night medicine again, sorry",
                "agent": "check_in_agent"
            }
        },
        {
            "signal_id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "timestamp": datetime.now(timezone.utc),
            "type": "chat",
            "data": {
                "role": "agent",
                "message": "No worries Ahmad! It happens. Try leaving your Atorvastatin next to your toothbrush so you see it before bed 😊",
                "agent": "check_in_agent"
            }
        },
        {
            "signal_id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "timestamp": datetime.now(timezone.utc),
            "type": "schedule_status",
            "data": {
                "task_id": "morning_amlodipine",
                "task_type": "meds",
                "status": "done",
                "cycle_id": 1
            }
        },
        {
            "signal_id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "timestamp": datetime.now(timezone.utc),
            "type": "schedule_status",
            "data": {
                "task_id": "night_atorvastatin",
                "task_type": "meds",
                "status": "missed",
                "cycle_id": 1
            }
        },
        {
            "signal_id": str(uuid.uuid4()),
            "patient_id": patient_id,
            "timestamp": datetime.now(timezone.utc),
            "type": "schedule_status",
            "data": {
                "task_id": "evening_walk",
                "task_type": "exercise",
                "status": "done",
                "cycle_id": 1
            }
        }
    ]

    # ── INSERT (clear first to avoid duplicates on re-seed) ──────────────────
    medical_records.delete_many({"patient_id": patient_id})
    patient_state.delete_many({"patient_id": patient_id})
    signals.delete_many({"patient_id": patient_id})

    medical_records.insert_one(med_record)
    patient_state.insert_one(pat_state)
    signals.insert_many(initial_signals)

    print(f"✅ Seeded patient {patient_id} — Ahmad Bin Sulaiman")
    print(f"   medical_records: 1 doc")
    print(f"   patient_state:   1 doc")
    print(f"   signals:         {len(initial_signals)} docs")

if __name__ == "__main__":
    seed_patient()
