import os
import sys
import json
import pickle
import numpy as np
import pandas as pd
from datetime import datetime, timezone
from sklearn.ensemble import GradientBoostingClassifier, GradientBoostingRegressor
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from sklearn.metrics import classification_report, mean_absolute_error
from dotenv import load_dotenv

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from db.connection import patient_state, medical_records

load_dotenv()

# ── PATHS ─────────────────────────────────────────────────────────────────────
MODEL_DIR = os.path.join(os.path.dirname(__file__))
CLASSIFIER_PATH = os.path.join(MODEL_DIR, "risk_classifier.pkl")
REGRESSOR_PATH = os.path.join(MODEL_DIR, "risk_regressor.pkl")
SCALER_PATH = os.path.join(MODEL_DIR, "scaler.pkl")

FEATURES = [
    "age", "bmi", "systolic_bp", "diastolic_bp",
    "cholesterol_mmol", "med_adherence_rate", "exercise_streak_days",
    "diet_adherence_rate", "stress_level", "smoking_status_encoded",
    "sleep_hours_avg"
]

# ── GENERATE SYNTHETIC TRAINING DATA ─────────────────────────────────────────
def generate_training_data(n: int = 2000) -> pd.DataFrame:
    """
    Generate medically grounded synthetic hypertension patient data.
    Based on known risk factors from NHANES and cardiovascular literature.
    """
    np.random.seed(42)

    age = np.random.normal(55, 12, n).clip(30, 80)
    bmi = np.random.normal(26, 4, n).clip(18, 45)
    systolic_bp = np.random.normal(140, 18, n).clip(100, 200)
    diastolic_bp = np.random.normal(88, 12, n).clip(60, 120)
    cholesterol = np.random.normal(5.5, 1.2, n).clip(2.5, 9.0)
    med_adherence = np.random.beta(3, 2, n)
    exercise_streak = np.random.poisson(3, n).clip(0, 30).astype(float)
    diet_adherence = np.random.beta(4, 2, n)
    stress_level = np.random.randint(1, 8, n).astype(float)
    smoking = np.random.choice([0, 1, 2], n, p=[0.5, 0.3, 0.2]).astype(float)
    sleep_hours = np.random.normal(6.5, 1.2, n).clip(3, 10)

    # medically grounded risk formula
    risk = (
        0.25 * (systolic_bp - 100) / 100 +
        0.20 * (1 - med_adherence) +
        0.15 * (age - 30) / 50 +
        0.10 * (bmi - 18) / 27 +
        0.10 * (cholesterol - 2.5) / 6.5 +
        0.08 * stress_level / 7 +
        0.07 * smoking / 2 +
        0.05 * (1 - diet_adherence)
    )
    risk = (risk - risk.min()) / (risk.max() - risk.min())
    high_risk = (risk > 0.6).astype(int)

    return pd.DataFrame({
        "age": age, "bmi": bmi,
        "systolic_bp": systolic_bp, "diastolic_bp": diastolic_bp,
        "cholesterol_mmol": cholesterol,
        "med_adherence_rate": med_adherence,
        "exercise_streak_days": exercise_streak,
        "diet_adherence_rate": diet_adherence,
        "stress_level": stress_level,
        "smoking_status_encoded": smoking,
        "sleep_hours_avg": sleep_hours,
        "risk_score": risk,
        "high_risk": high_risk
    })

# ── TRAIN ─────────────────────────────────────────────────────────────────────
def train_models():
    print("🏋️  Training risk models...")
    df = generate_training_data(2000)

    X = df[FEATURES]
    y_class = df["high_risk"]
    y_reg = df["risk_score"]

    X_train, X_test, yc_train, yc_test, yr_train, yr_test = train_test_split(
        X, y_class, y_reg, test_size=0.2, random_state=42
    )

    # scale features
    scaler = StandardScaler()
    X_train_sc = scaler.fit_transform(X_train)
    X_test_sc = scaler.transform(X_test)

    # classifier: high risk vs not
    clf = GradientBoostingClassifier(n_estimators=100, max_depth=4, random_state=42)
    clf.fit(X_train_sc, yc_train)
    clf_preds = clf.predict(X_test_sc)
    print("\n📊 Classifier Report:")
    print(classification_report(yc_test, clf_preds, target_names=["low/med risk", "high risk"]))

    # regressor: exact 0-1 risk score
    reg = GradientBoostingRegressor(n_estimators=100, max_depth=4, random_state=42)
    reg.fit(X_train_sc, yr_train)
    reg_preds = reg.predict(X_test_sc)
    mae = mean_absolute_error(yr_test, reg_preds)
    print(f"📊 Regressor MAE: {mae:.4f}")

    # feature importance
    importances = dict(zip(FEATURES, clf.feature_importances_))
    top = sorted(importances.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"\n🔍 Top 5 risk factors: {[f[0] for f in top]}")

    # save models
    with open(CLASSIFIER_PATH, "wb") as f:
        pickle.dump(clf, f)
    with open(REGRESSOR_PATH, "wb") as f:
        pickle.dump(reg, f)
    with open(SCALER_PATH, "wb") as f:
        pickle.dump(scaler, f)

    print(f"\n✅ Models saved to {MODEL_DIR}")
    return clf, reg, scaler

# ── LOAD ──────────────────────────────────────────────────────────────────────
def load_models():
    if not all(os.path.exists(p) for p in [CLASSIFIER_PATH, REGRESSOR_PATH, SCALER_PATH]):
        print("⚠️  Models not found, training now...")
        return train_models()

    with open(CLASSIFIER_PATH, "rb") as f:
        clf = pickle.load(f)
    with open(REGRESSOR_PATH, "rb") as f:
        reg = pickle.load(f)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    return clf, reg, scaler

# ── PREDICT FOR ONE PATIENT ───────────────────────────────────────────────────
def predict_risk(patient_id: str) -> dict:
    """
    Reads ml_features from patient_state DB,
    runs risk model, stores result back in patient_state.
    This runs async/background — Plan Agent reads it next cycle.
    """
    clf, reg, scaler = load_models()

    # read ml_features saved by plan agent
    state = patient_state.find_one({"patient_id": patient_id}, {"_id": 0})
    if not state:
        return {"error": f"patient {patient_id} not found"}

    features = state.get("ml_features", {})
    if not features or "systolic_bp" not in features:
        # fallback: build features directly from state + medical records
        print("   ⚠️  ml_features not found, building from raw state...")
        med = medical_records.find_one({"patient_id": patient_id}, {"_id": 0})
        if not med:
            return {"error": "medical records not found"}

        habits = state.get("habits", {})
        bp = habits.get("last_bp_reading", {})
        smoking_map = {"never": 0, "ex-smoker": 1, "current": 2}

        features = {
            "age": med["personal"].get("age", 50),
            "bmi": med["personal"].get("bmi", 25.0),
            "systolic_bp": bp.get("systolic", 140),
            "diastolic_bp": bp.get("diastolic", 90),
            "cholesterol_mmol": med["labs"].get("cholesterol_mmol", 5.0),
            "med_adherence_rate": habits.get("med_adherence_rate", 0.5),
            "exercise_streak_days": habits.get("exercise_streak_days", 0),
            "diet_adherence_rate": habits.get("diet_adherence_rate", 0.5),
            "stress_level": habits.get("stress_level_reported", 3),
            "smoking_status_encoded": smoking_map.get(
                med["personal"].get("smoking_status", "never"), 0
            ),
            "sleep_hours_avg": habits.get("sleep_hours_avg", 7.0),
        }

    # build feature vector in correct order
    feature_vector = [[features.get(f, 0) for f in FEATURES]]
    df_input = pd.DataFrame(feature_vector, columns=FEATURES)

    # scale and predict
    X_scaled = scaler.transform(df_input)
    risk_score = float(reg.predict(X_scaled)[0])
    risk_score = round(max(0.0, min(1.0, risk_score)), 4)  # clamp 0-1
    high_risk_prob = float(clf.predict_proba(X_scaled)[0][1])
    risk_label = "high" if risk_score > 0.65 else "medium" if risk_score > 0.40 else "low"

    result = {
        "value": risk_score,
        "label": risk_label,
        "high_risk_probability": round(high_risk_prob, 4),
        "computed_at": datetime.now(timezone.utc).isoformat(),
        "features_used": FEATURES,
        "top_risk_factors": _get_top_risk_factors(clf, df_input, X_scaled)
    }

    # write back to patient_state — Plan Agent reads this next cycle
    patient_state.update_one(
        {"patient_id": patient_id},
        {"$set": {
            "risk_score": result,
            "last_updated": datetime.now(timezone.utc)
        }}
    )

    print(f"✅ Risk score computed for {patient_id}: {risk_score} ({risk_label})")
    print(f"   High risk probability: {high_risk_prob:.2%}")
    print(f"   Top risk factors: {result['top_risk_factors']}")

    return result

def _get_top_risk_factors(clf, df_input: pd.DataFrame, X_scaled) -> list:
    """Return top 3 contributing risk factors for this patient"""
    importances = clf.feature_importances_
    feature_contributions = []
    for i, feat in enumerate(FEATURES):
        feature_contributions.append((feat, float(importances[i] * abs(X_scaled[0][i]))))
    top3 = sorted(feature_contributions, key=lambda x: x[1], reverse=True)[:3]
    return [f[0] for f in top3]

# ── RUN FOR ALL PATIENTS (background job) ────────────────────────────────────
def run_risk_scoring_cycle():
    """Run risk scoring for all patients in DB — called as background job"""
    print("\n🔄 Running risk scoring cycle...")
    all_patients = list(patient_state.find({}, {"patient_id": 1, "_id": 0}))
    print(f"   Found {len(all_patients)} patients")

    results = []
    for p in all_patients:
        pid = p["patient_id"]
        result = predict_risk(pid)
        results.append({"patient_id": pid, **result})

    print(f"\n✅ Risk scoring cycle complete for {len(results)} patients")
    return results

if __name__ == "__main__":
    # train models first
    train_models()
    print("\n" + "─"*50)
    # run scoring for p001
    result = predict_risk("p001")
    print(f"\nFinal risk result: {json.dumps(result, indent=2, default=str)}")
