import { useState } from "react";
import axios from "axios";

export default function Login({ onLogin }) {
  const [id, setId]         = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError]   = useState("");

  const handleLogin = async () => {
    setLoading(true);
    setError("");
    try {
      // use typed id or default to p001
      const patientId = id.trim() || "p001";
      const res = await axios.get(`http://localhost:8000/patient/${patientId}`);
      onLogin(res.data);
    } catch (e) {
      setError("Patient not found. Try 'p001'");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--beige)",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      flexDirection: "column",
      gap: "2rem",
    }}>
      {/* LOGO */}
      <div style={{ textAlign: "center" }}>
        <div style={{ fontSize: "3.5rem", marginBottom: "0.5rem" }}>🌿</div>
        <h1 style={{
          fontFamily: "'DM Serif Display', serif",
          color: "var(--dark-green)",
          fontSize: "2.8rem",
          lineHeight: 1.1
        }}>
          CareCompanion
        </h1>
        <p style={{
          color: "var(--text-secondary)",
          marginTop: "0.5rem",
          fontSize: "1rem",
          fontWeight: 300
        }}>
          Your personal hypertension care companion
        </p>
      </div>

      {/* LOGIN CARD */}
      <div style={{
        background: "var(--card-bg)",
        border: "1.5px solid var(--border)",
        borderRadius: "var(--radius)",
        padding: "2.5rem",
        width: "360px",
        boxShadow: "var(--shadow)",
        display: "flex",
        flexDirection: "column",
        gap: "1.25rem"
      }}>
        <div>
          <label style={{
            display: "block",
            fontSize: "0.8rem",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: "0.5rem"
          }}>
            Patient ID
          </label>
          <input
            value={id}
            onChange={e => setId(e.target.value)}
            onKeyDown={e => e.key === "Enter" && handleLogin()}
            placeholder="e.g. p001"
            style={{
              width: "100%",
              padding: "0.75rem 1rem",
              borderRadius: "var(--radius-sm)",
              border: "1.5px solid var(--border)",
              background: "var(--beige)",
              color: "var(--dark-green)",
              fontSize: "1rem",
              fontFamily: "'DM Sans', sans-serif",
              outline: "none",
            }}
          />
        </div>

        <div>
          <label style={{
            display: "block",
            fontSize: "0.8rem",
            fontWeight: 600,
            color: "var(--text-muted)",
            textTransform: "uppercase",
            letterSpacing: "0.08em",
            marginBottom: "0.5rem"
          }}>
            Password
          </label>
          <input
            type="password"
            placeholder="••••••••"
            style={{
              width: "100%",
              padding: "0.75rem 1rem",
              borderRadius: "var(--radius-sm)",
              border: "1.5px solid var(--border)",
              background: "var(--beige)",
              color: "var(--dark-green)",
              fontSize: "1rem",
              fontFamily: "'DM Sans', sans-serif",
              outline: "none",
            }}
          />
        </div>

        {error && (
          <p style={{ color: "var(--rosy)", fontSize: "0.85rem", textAlign: "center" }}>
            {error}
          </p>
        )}

        <button onClick={handleLogin} disabled={loading} style={{
          background: "var(--dark-green)",
          color: "var(--beige)",
          border: "none",
          borderRadius: "var(--radius-sm)",
          padding: "0.85rem",
          fontSize: "1rem",
          fontFamily: "'DM Sans', sans-serif",
          fontWeight: 600,
          cursor: loading ? "not-allowed" : "pointer",
          opacity: loading ? 0.7 : 1,
          transition: "all 0.2s ease",
        }}>
          {loading ? "Signing in..." : "Sign In"}
        </button>
      </div>

      <p style={{ color: "var(--text-muted)", fontSize: "0.8rem" }}>
        Demo: use patient ID <strong>p001</strong>
      </p>
    </div>
  );
}
