import { useState, useCallback } from "react";
import axios from "axios";
import Login from "./pages/Login";
import Dashboard from "./pages/Dashboard";
import Chat from "./pages/Chat";
import Schedule from "./pages/Schedule";
import Summary from "./pages/Summary";
import "./index.css";

const TABS = [
  { id: "dashboard", label: "Dashboard" },
  { id: "chat",      label: "Chat" },
  { id: "schedule",  label: "Schedule" },
  { id: "summary",   label: "Summary" },
];

export default function App() {
  const [page, setPage]           = useState("login");
  const [patient, setPatient]     = useState(null);
  const [activeTab, setActiveTab] = useState("dashboard");

  const handleLogin = (patientData) => {
    setPatient(patientData);
    setPage("app");
  };

  // refresh patient data from DB — called after task updates
  const refreshPatient = useCallback(async () => {
    if (!patient?.patient_id) return;
    try {
      const res = await axios.get(`http://localhost:8000/patient/${patient.patient_id}`);
      setPatient(res.data);
    } catch(e) {
      console.error("Failed to refresh patient", e);
    }
  }, [patient?.patient_id]);

  if (page === "login") return <Login onLogin={handleLogin} />;

  return (
    <div style={{ minHeight: "100vh", background: "var(--beige)" }}>
      <nav style={{
        background: "var(--dark-green)", padding: "0 2rem",
        display: "flex", alignItems: "center", justifyContent: "space-between",
        height: "64px", boxShadow: "0 2px 12px rgba(10,51,35,0.15)",
        position: "sticky", top: 0, zIndex: 100,
      }}>
        <span style={{ fontFamily: "'DM Serif Display', serif", color: "var(--beige)", fontSize: "1.3rem", letterSpacing: "0.5px" }}>
          🌿 CareCompanion
        </span>
        <div style={{ display: "flex", gap: "0.25rem" }}>
          {TABS.map(tab => (
            <button key={tab.id} onClick={() => setActiveTab(tab.id)} style={{
              background: activeTab === tab.id ? "var(--moss-green)" : "transparent",
              color: activeTab === tab.id ? "var(--beige)" : "rgba(247,244,213,0.6)",
              border: "none", padding: "0.5rem 1.2rem", borderRadius: "8px",
              cursor: "pointer", fontFamily: "'DM Sans', sans-serif",
              fontWeight: activeTab === tab.id ? "600" : "400",
              fontSize: "0.9rem", transition: "all 0.2s ease",
            }}>{tab.label}</button>
          ))}
        </div>
        <span style={{ color: "var(--beige)", fontSize: "0.85rem", opacity: 0.85, fontWeight: 500 }}>
          Welcome, {patient?.name?.split(" ")[0]} 👋
        </span>
      </nav>

      <main style={{ padding: "2rem", maxWidth: "1100px", margin: "0 auto" }}>
        {activeTab === "dashboard" && <Dashboard patient={patient} />}
        {activeTab === "chat"      && <Chat patientId={patient?.patient_id} />}
        {activeTab === "schedule"  && <Schedule patientId={patient?.patient_id} patient={patient} onRefresh={refreshPatient} />}
        {activeTab === "summary"   && <Summary patient={patient} onRefresh={refreshPatient} />}
      </main>
    </div>
  );
}
