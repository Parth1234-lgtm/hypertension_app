export default function Dashboard({ patient }) {
  if (!patient) return null;

  const risk = patient.risk_score || {};
  const habits = patient.habits || {};
  const flags = patient.priority_flags || [];

  const riskColor = {
    high: "var(--rosy)",
    medium: "#e8a838",
    low: "var(--moss-green)"
  }[risk.label] || "var(--moss-green)";

  const stats = [
    {
      label: "Risk Score",
      value: risk.value ? `${(risk.value * 100).toFixed(0)}%` : "—",
      sub: risk.label || "—",
      color: riskColor,
      icon: "🫀"
    },
    {
      label: "Med Adherence",
      value: habits.med_adherence_rate ? `${(habits.med_adherence_rate * 100).toFixed(0)}%` : "—",
      sub: habits.med_adherence_rate >= 0.7 ? "On track" : "Needs attention",
      color: habits.med_adherence_rate >= 0.7 ? "var(--moss-green)" : "var(--rosy)",
      icon: "💊"
    },
    {
      label: "Last BP",
      value: habits.last_bp_reading ? `${habits.last_bp_reading.systolic}/${habits.last_bp_reading.diastolic}` : "—",
      sub: "mmHg",
      color: "var(--midnight)",
      icon: "📊"
    },
    {
      label: "Exercise Streak",
      value: `${habits.exercise_streak_days || 0}`,
      sub: "days",
      color: "var(--moss-green)",
      icon: "🏃"
    },
  ];

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>

      {/* WELCOME */}
      <div style={{
        background: "var(--dark-green)",
        borderRadius: "var(--radius)",
        padding: "2.5rem",
        color: "var(--beige)",
        position: "relative",
        overflow: "hidden"
      }}>
        <div style={{
          position: "absolute", top: "-40px", right: "-40px",
          width: "200px", height: "200px",
          borderRadius: "50%",
          background: "rgba(131,153,88,0.15)"
        }} />
        <div style={{
          position: "absolute", bottom: "-60px", right: "100px",
          width: "150px", height: "150px",
          borderRadius: "50%",
          background: "rgba(16,86,102,0.2)"
        }} />
        <p style={{ opacity: 0.7, fontSize: "0.9rem", marginBottom: "0.5rem" }}>
          Good day,
        </p>
        <h1 style={{
          fontFamily: "'DM Serif Display', serif",
          fontSize: "2.2rem",
          marginBottom: "0.75rem"
        }}>
          {patient.name} 🌿
        </h1>
        <p style={{ opacity: 0.75, fontSize: "0.95rem", maxWidth: "500px" }}>
          Managing <strong>{patient.conditions?.join(", ")}</strong> · Age {patient.age}
        </p>
        {flags.length > 0 && (
          <div style={{ marginTop: "1.25rem", display: "flex", gap: "0.5rem", flexWrap: "wrap" }}>
            {flags.map(f => (
              <span key={f} style={{
                background: "rgba(211,150,140,0.25)",
                color: "#f5c4bc",
                borderRadius: "20px",
                padding: "0.25rem 0.75rem",
                fontSize: "0.75rem",
                fontWeight: 500
              }}>
                ⚠️ {f.replace(/_/g, " ")}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* STATS GRID */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(4, 1fr)",
        gap: "1rem"
      }}>
        {stats.map(stat => (
          <div key={stat.label} style={{
            background: "var(--card-bg)",
            border: "1.5px solid var(--border)",
            borderRadius: "var(--radius)",
            padding: "1.5rem",
            boxShadow: "var(--shadow)",
          }}>
            <div style={{ fontSize: "1.8rem", marginBottom: "0.75rem" }}>{stat.icon}</div>
            <div style={{
              fontSize: "2rem",
              fontFamily: "'DM Serif Display', serif",
              color: stat.color,
              lineHeight: 1
            }}>
              {stat.value}
            </div>
            <div style={{ fontSize: "0.75rem", color: "var(--text-muted)", marginTop: "0.25rem" }}>
              {stat.sub}
            </div>
            <div style={{
              fontSize: "0.8rem",
              color: "var(--text-secondary)",
              marginTop: "0.5rem",
              fontWeight: 500
            }}>
              {stat.label}
            </div>
          </div>
        ))}
      </div>

      {/* TODAY'S MEDS QUICK VIEW */}
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
          Today's Medications
        </h3>
        <div style={{ display: "flex", flexDirection: "column", gap: "0.75rem" }}>
          {patient.schedule?.meds?.map(med => (
            <div key={med.task_id} style={{
              display: "flex",
              alignItems: "center",
              justifyContent: "space-between",
              padding: "0.75rem 1rem",
              background: "var(--beige)",
              borderRadius: "var(--radius-sm)",
              border: "1px solid var(--border)"
            }}>
              <div style={{ display: "flex", alignItems: "center", gap: "0.75rem" }}>
                <span style={{ fontSize: "1.2rem" }}>💊</span>
                <div>
                  <div style={{ fontWeight: 500, fontSize: "0.9rem" }}>{med.name}</div>
                  <div style={{ fontSize: "0.75rem", color: "var(--text-muted)" }}>{med.timing}</div>
                </div>
              </div>
              <span style={{
                background: med.priority === "critical" ? "rgba(211,150,140,0.2)" : "rgba(131,153,88,0.15)",
                color: med.priority === "critical" ? "var(--rosy)" : "var(--moss-green)",
                borderRadius: "20px",
                padding: "0.2rem 0.6rem",
                fontSize: "0.7rem",
                fontWeight: 600,
                textTransform: "uppercase"
              }}>
                {med.priority || "normal"}
              </span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
