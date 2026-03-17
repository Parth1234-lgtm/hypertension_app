import { useState } from "react";
import axios from "axios";

export default function Summary({ patient, onRefresh }) {
  const [running, setRunning] = useState(false);
  const [cycleResult, setCycleResult] = useState(null);

  if (!patient) return null;

  const avatar = patient.avatar_state || { mood: "okay", gif: "okay.gif", message: "Stay consistent 🙂", color: "#eab308" };
  const risk = patient.risk_score || {};
  const habits = patient.habits || {};
  const summary = patient.latest_clinical_summary || "";
  const flags = patient.priority_flags || [];

  const runCycle = async () => {
    setRunning(true);
    try {
      const res = await axios.post("http://localhost:8000/quick-refresh", {
        patient_id: patient.patient_id
      });
      setCycleResult(res.data);
      if (onRefresh) await onRefresh();
    } catch (e) {
      console.error("Cycle failed", e);
    } finally {
      setRunning(false);
    }
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>

      {/* TOP ROW — avatar + health stats */}
      <div style={{ display: "grid", gridTemplateColumns: "300px 1fr", gap: "1.5rem" }}>

        {/* AVATAR CARD */}
        <div style={{
          background: "var(--card-bg)",
          border: "1.5px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "2rem",
          boxShadow: "var(--shadow)",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "1rem",
          textAlign: "center"
        }}>
          <div style={{
            width: "220px",
            height: "220px",
            borderRadius: "50%",
            background: `${avatar.color}18`,
            border: `3px solid ${avatar.color}40`,
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            overflow: "hidden"
          }}>
            <img
              src={`/avatars/${avatar.gif || "okay.gif"}`}
              alt={avatar.mood}
              style={{ width: "200px", height: "200px", objectFit: "contain" }}
            />
          </div>

          <div>
            <div style={{
              display: "inline-block",
              background: `${avatar.color}20`,
              color: avatar.color,
              borderRadius: "20px",
              padding: "0.3rem 1rem",
              fontSize: "0.8rem",
              fontWeight: 700,
              textTransform: "uppercase",
              letterSpacing: "0.06em",
              marginBottom: "0.5rem"
            }}>
              {avatar.mood}
            </div>
            <p style={{
              color: "var(--text-secondary)",
              fontSize: "0.9rem",
              lineHeight: 1.4
            }}>
              {avatar.message}
            </p>
          </div>

          {/* RUN CYCLE BUTTON */}
          <button onClick={runCycle} disabled={running} style={{
            background: "var(--dark-green)",
            color: "var(--beige)",
            border: "none",
            borderRadius: "var(--radius-sm)",
            padding: "0.55rem 1.2rem",
            fontSize: "0.8rem",
            fontWeight: 600,
            fontFamily: "'DM Sans', sans-serif",
            cursor: running ? "not-allowed" : "pointer",
            opacity: running ? 0.6 : 1,
            width: "100%",
            transition: "all 0.2s"
          }}>
            {running ? "⏳ Generating..." : "⚡ Quick Refresh"}
          </button>

          {cycleResult && (
            <div style={{
              background: "rgba(131,153,88,0.1)",
              border: "1px solid var(--moss-green)",
              borderRadius: "var(--radius-sm)",
              padding: "0.75rem",
              fontSize: "0.8rem",
              color: "var(--moss-green)",
              width: "100%",
              textAlign: "left"
            }}>
              ✅ Cycle complete!<br />
              Risk: {cycleResult.risk_score ? `${(cycleResult.risk_score * 100).toFixed(0)}%` : "—"} ({cycleResult.risk_label})<br />
              Avatar: {cycleResult.avatar_state}
            </div>
          )}
        </div>

        {/* HEALTH STATS */}
        <div style={{
          background: "var(--card-bg)",
          border: "1.5px solid var(--border)",
          borderRadius: "var(--radius)",
          padding: "1.75rem",
          boxShadow: "var(--shadow)",
        }}>
          <h3 style={{
            fontFamily: "'DM Serif Display', serif",
            fontSize: "1.2rem",
            color: "var(--dark-green)",
            marginBottom: "1.25rem"
          }}>
            Health Overview
          </h3>

          <div style={{ display: "flex", flexDirection: "column", gap: "1rem" }}>
            {[
              { label: "Risk Score", value: risk.value ? `${(risk.value * 100).toFixed(0)}%` : "—", sub: risk.label, color: risk.label === "high" ? "var(--rosy)" : risk.label === "medium" ? "#e8a838" : "var(--moss-green)" },
              { label: "Blood Pressure", value: habits.last_bp_reading ? `${habits.last_bp_reading.systolic}/${habits.last_bp_reading.diastolic}` : "—", sub: "mmHg · target <130/80", color: "var(--midnight)" },
              { label: "Medication Adherence", value: habits.med_adherence_rate ? `${(habits.med_adherence_rate * 100).toFixed(0)}%` : "—", sub: "of doses taken", color: habits.med_adherence_rate >= 0.7 ? "var(--moss-green)" : "var(--rosy)" },
              { label: "Diet Adherence", value: habits.diet_adherence_rate ? `${(habits.diet_adherence_rate * 100).toFixed(0)}%` : "—", sub: "of meals followed", color: "var(--moss-green)" },
              { label: "Exercise Streak", value: `${habits.exercise_streak_days || 0} days`, sub: "consecutive days active", color: "var(--midnight)" },
            ].map(item => (
              <div key={item.label} style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                padding: "0.75rem 1rem",
                background: "var(--beige)",
                borderRadius: "var(--radius-sm)",
                border: "1px solid var(--border)"
              }}>
                <div>
                  <div style={{ fontSize: "0.8rem", fontWeight: 500, color: "var(--text-primary)" }}>{item.label}</div>
                  <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>{item.sub}</div>
                </div>
                <div style={{
                  fontFamily: "'DM Serif Display', serif",
                  fontSize: "1.4rem",
                  color: item.color
                }}>
                  {item.value}
                </div>
              </div>
            ))}
          </div>

          {/* FLAGS */}
          {flags.length > 0 && (
            <div style={{ marginTop: "1rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
              {flags.map(f => (
                <span key={f} style={{
                  background: "rgba(211,150,140,0.15)",
                  color: "var(--rosy)",
                  borderRadius: "20px",
                  padding: "0.25rem 0.75rem",
                  fontSize: "0.72rem",
                  fontWeight: 600
                }}>
                  ⚠️ {f.replace(/_/g, " ")}
                </span>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* CLINICAL SUMMARY */}
      <div style={{
        background: "var(--card-bg)",
        border: "1.5px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "1.75rem",
        boxShadow: "var(--shadow)",
      }}>
        <h3 style={{
          fontFamily: "'DM Serif Display', serif",
          fontSize: "1.2rem",
          color: "var(--dark-green)",
          marginBottom: "1rem"
        }}>
          Clinical Summary
        </h3>
        {summary ? (
          <pre style={{
            fontFamily: "'DM Sans', sans-serif",
            fontSize: "0.88rem",
            color: "var(--text-secondary)",
            lineHeight: 1.7,
            whiteSpace: "pre-wrap",
            wordBreak: "break-word",
            background: "var(--beige)",
            borderRadius: "var(--radius-sm)",
            padding: "1.25rem",
            border: "1px solid var(--border)"
          }}>
            {summary}
          </pre>
        ) : (
          <div style={{
            background: "var(--beige)",
            borderRadius: "var(--radius-sm)",
            padding: "2rem",
            textAlign: "center",
            color: "var(--text-muted)",
            border: "1px solid var(--border)",
            fontSize: "0.9rem"
          }}>
            No clinical summary yet. Run a cycle to generate one 👆
          </div>
        )}
      </div>
    </div>
  );
}
