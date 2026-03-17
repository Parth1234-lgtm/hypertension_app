import { useState, useEffect } from "react";
import axios from "axios";

const TYPE_ICONS = { meds: "💊", food: "🥗", exercise: "🏃" };
const TYPE_LABELS = { meds: "Medication", food: "Meal", exercise: "Exercise" };

export default function Schedule({ patientId, patient, onRefresh }) {
  const [notifications, setNotifications] = useState([]);
  const [tasks, setTasks]                 = useState([]);
  const [updated, setUpdated]             = useState({});
  const [permissionStatus, setPermissionStatus] = useState("default");
  const [scheduledNotifs, setScheduledNotifs]   = useState([]);
  const [refreshing, setRefreshing]             = useState(false);

  useEffect(() => {
    if ("Notification" in window) setPermissionStatus(Notification.permission);
    axios.get(`http://localhost:8000/notifications/${patientId}`)
      .then(res => setNotifications(res.data.notifications || []));

    if (patient?.schedule) {
      const allTasks = [
        ...(patient.schedule.meds || []).map(t => ({ ...t, category: "meds" })),
        ...(patient.schedule.food || []).map(t => ({ ...t, category: "food" })),
        ...(patient.schedule.exercise || []).map(t => ({ ...t, category: "exercise" })),
      ];
      setTasks(allTasks);

      // ── load persisted statuses from DB via signals ──
      axios.get(`http://localhost:8000/task-statuses/${patientId}`)
        .then(res => {
          if (res.data.statuses) setUpdated(res.data.statuses);
        }).catch(() => {});

      scheduleTaskNotifications(allTasks);
    }
  }, [patientId, patient]);

  const requestPermission = async () => {
    if (!("Notification" in window)) return;
    const result = await Notification.requestPermission();
    setPermissionStatus(result);
  };

  const scheduleTaskNotifications = (taskList) => {
    if (Notification.permission !== "granted") return;
    const now = new Date();
    const scheduled = [];
    taskList.forEach(task => {
      const timing = task.timing;
      if (!timing || !timing.match(/^\d{2}:\d{2}$/)) return;
      const [hours, mins] = timing.split(":").map(Number);
      const taskTime = new Date();
      taskTime.setHours(hours, mins, 0, 0);
      const msUntil = taskTime - now;
      if (msUntil <= 0) return;
      const taskName = task.name || task.type || task.meal || task.task_id;
      setTimeout(() => {
        new Notification("CareCompanion Reminder 🌿", {
          body: `${TYPE_ICONS[task.category]} Time for: ${taskName}`,
          tag: task.task_id,
        });
      }, msUntil);
      scheduled.push({ task_id: task.task_id, name: taskName, timing, minsUntil: Math.round(msUntil / 60000) });
    });
    setScheduledNotifs(scheduled);
  };

  const fireTestNotification = (task) => {
    if (Notification.permission !== "granted") { requestPermission(); return; }
    const taskName = task.name || task.type || task.meal || task.task_id;
    new Notification("CareCompanion Reminder 🌿", {
      body: `${TYPE_ICONS[task.category]} Time for: ${taskName}`,
      tag: task.task_id + "_test",
    });
  };

  const markTask = async (task, status) => {
    try {
      await axios.post("http://localhost:8000/schedule/status", {
        patient_id: patientId,
        task_id: task.task_id,
        task_type: task.category,
        status,
        cycle_id: patient?.current_cycle_id || 1
      });
      const nextUpdated = { ...updated, [task.task_id]: status };
      setUpdated(nextUpdated);

      // auto quick refresh after marking task so avatar + stats update
      setRefreshing(true);
      try {
        await axios.post("http://localhost:8000/quick-refresh", { patient_id: patientId });
        if (onRefresh) await onRefresh(); // tell App.jsx to reload patient data
      } catch(e) { console.error("refresh failed", e); }
      finally { setRefreshing(false); }

      // If all tasks have been marked (done/missed), trigger a FULL cycle
      // so Plan Agent can generate a NEW schedule for the demo.
      const allMarked = tasks.length > 0 && tasks.every(t => (nextUpdated[t.task_id] || t.status) && (nextUpdated[t.task_id] || t.status) !== "pending");
      if (allMarked) {
        try {
          await axios.post("http://localhost:8000/run-cycle", { patient_id: patientId });
          // give background cycle a moment, then refresh patient to load new schedule/avatar
          setTimeout(() => { if (onRefresh) onRefresh(); }, 5000);
        } catch (e) {
          console.error("full cycle trigger failed", e);
        }
      }

    } catch (e) {
      console.error("Failed to update task", e);
    }
  };

  const getTaskStatus = (task) => updated[task.task_id] || task.status || "pending";
  const getTaskLabel = (task) => {
    if (task.category === "meds") return task.name;
    if (task.category === "food") return `${task.meal?.charAt(0).toUpperCase() + task.meal?.slice(1)}: ${task.options?.[0]}`;
    if (task.category === "exercise") return `${task.type} — ${task.duration_mins} mins`;
    return task.task_id;
  };
  const getTaskTime = (task) => {
    if (task.timing) return task.timing;
    if (task.meal === "breakfast") return "Morning";
    if (task.meal === "lunch") return "Afternoon";
    if (task.meal === "dinner") return "Evening";
    return "—";
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: "1.5rem" }}>

      {/* REFRESHING INDICATOR */}
      {refreshing && (
        <div style={{
          background: "rgba(131,153,88,0.1)", border: "1.5px solid var(--moss-green)",
          borderRadius: "var(--radius)", padding: "0.75rem 1.25rem",
          fontSize: "0.85rem", color: "var(--moss-green)", fontWeight: 500, textAlign: "center"
        }}>
          ⚡ Updating your health summary...
        </div>
      )}

      {/* NOTIFICATION PERMISSION BANNER */}
      {permissionStatus !== "granted" && (
        <div style={{
          background: "var(--card-bg)", border: "1.5px solid var(--border)",
          borderRadius: "var(--radius)", padding: "1rem 1.5rem",
          display: "flex", alignItems: "center", justifyContent: "space-between",
          boxShadow: "var(--shadow)"
        }}>
          <div>
            <div style={{ fontWeight: 600, fontSize: "0.9rem", color: "var(--dark-green)" }}>🔔 Enable Reminders</div>
            <div style={{ fontSize: "0.78rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
              Allow notifications to get timed reminders for your medications and tasks
            </div>
          </div>
          <button onClick={requestPermission} style={{
            background: "var(--dark-green)", color: "var(--beige)", border: "none",
            borderRadius: "var(--radius-sm)", padding: "0.6rem 1.2rem",
            fontSize: "0.85rem", fontWeight: 600, cursor: "pointer",
            fontFamily: "'DM Sans', sans-serif", whiteSpace: "nowrap"
          }}>Enable</button>
        </div>
      )}

      {/* SCHEDULED NOTIFS STATUS */}
      {permissionStatus === "granted" && scheduledNotifs.length > 0 && (
        <div style={{
          background: "rgba(131,153,88,0.08)", border: "1.5px solid var(--moss-green)",
          borderRadius: "var(--radius)", padding: "0.75rem 1.25rem",
          fontSize: "0.82rem", color: "var(--moss-green)", fontWeight: 500
        }}>
          ✅ {scheduledNotifs.length} reminder{scheduledNotifs.length > 1 ? "s" : ""} scheduled today —{" "}
          {scheduledNotifs.map(n => `${n.name} at ${n.timing}`).join(", ")}
        </div>
      )}

      {/* REMINDERS BAR */}
      {notifications.length > 0 && (
        <div style={{
          background: "var(--midnight)", borderRadius: "var(--radius)",
          padding: "1.25rem 1.5rem", display: "flex", flexDirection: "column", gap: "0.6rem"
        }}>
          <h3 style={{ fontFamily: "'DM Serif Display', serif", color: "var(--beige)", fontSize: "1rem", marginBottom: "0.25rem" }}>
            📬 Today's Reminders
          </h3>
          {notifications.map(n => (
            <div key={n.id} style={{
              display: "flex", alignItems: "center", justifyContent: "space-between",
              background: "rgba(247,244,213,0.08)", borderRadius: "var(--radius-sm)", padding: "0.6rem 1rem",
            }}>
              <span style={{ color: "var(--beige)", fontSize: "0.88rem" }}>{n.message}</span>
              <span style={{
                background: n.priority === "critical" ? "rgba(211,150,140,0.3)" : "rgba(131,153,88,0.25)",
                color: n.priority === "critical" ? "#f5c4bc" : "#c5d9a0",
                borderRadius: "20px", padding: "0.2rem 0.6rem", fontSize: "0.7rem", fontWeight: 600
              }}>{n.timing}</span>
            </div>
          ))}
        </div>
      )}

      {/* SCHEDULE TABLE */}
      <div style={{
        background: "var(--card-bg)", border: "1.5px solid var(--border)",
        borderRadius: "var(--radius)", boxShadow: "var(--shadow)", overflow: "hidden"
      }}>
        <div style={{
          padding: "1.25rem 1.5rem", borderBottom: "1.5px solid var(--border)",
          display: "flex", alignItems: "center", justifyContent: "space-between"
        }}>
          <h3 style={{ fontFamily: "'DM Serif Display', serif", fontSize: "1.2rem", color: "var(--dark-green)" }}>
            Today's Schedule
          </h3>
          <span style={{ fontSize: "0.8rem", color: "var(--text-muted)" }}>
            {Object.values(updated).filter(v => v === "done").length} / {tasks.length} completed
          </span>
        </div>

        <div style={{
          display: "grid", gridTemplateColumns: "60px 1fr 100px 180px 120px",
          padding: "0.6rem 1.5rem", background: "var(--beige)", borderBottom: "1px solid var(--border)",
          fontSize: "0.72rem", fontWeight: 600, color: "var(--text-muted)",
          textTransform: "uppercase", letterSpacing: "0.07em"
        }}>
          <span>Type</span><span>Task</span><span>Time</span>
          <span style={{ textAlign: "center" }}>Status</span>
          <span style={{ textAlign: "center" }}>Test Notif</span>
        </div>

        {tasks.map(task => {
          const status = getTaskStatus(task);
          return (
            <div key={task.task_id} style={{
              display: "grid", gridTemplateColumns: "60px 1fr 100px 180px 120px",
              padding: "1rem 1.5rem", borderBottom: "1px solid var(--border)",
              alignItems: "center",
              background: status === "done" ? "rgba(131,153,88,0.06)" : "transparent",
              transition: "background 0.2s"
            }}>
              <span style={{ fontSize: "1.3rem" }}>{TYPE_ICONS[task.category]}</span>
              <div>
                <div style={{
                  fontSize: "0.9rem", fontWeight: 500, color: "var(--dark-green)",
                  textDecoration: status === "done" ? "line-through" : "none",
                  opacity: status === "done" ? 0.5 : 1
                }}>{getTaskLabel(task)}</div>
                <div style={{ fontSize: "0.72rem", color: "var(--text-muted)" }}>
                  {TYPE_LABELS[task.category]}
                  {task.priority === "critical" && (
                    <span style={{ color: "var(--rosy)", marginLeft: "0.4rem" }}>• critical</span>
                  )}
                </div>
              </div>
              <span style={{ fontSize: "0.85rem", color: "var(--text-secondary)" }}>{getTaskTime(task)}</span>
              <div style={{ display: "flex", gap: "0.5rem", justifyContent: "center" }}>
                {status === "done" ? (
                  <span style={{ background: "rgba(131,153,88,0.15)", color: "var(--moss-green)", borderRadius: "20px", padding: "0.3rem 0.9rem", fontSize: "0.8rem", fontWeight: 600 }}>✅ Done</span>
                ) : status === "missed" ? (
                  <span style={{ background: "rgba(211,150,140,0.15)", color: "var(--rosy)", borderRadius: "20px", padding: "0.3rem 0.9rem", fontSize: "0.8rem", fontWeight: 600 }}>❌ Missed</span>
                ) : (
                  <>
                    <button onClick={() => markTask(task, "done")} style={{ background: "rgba(131,153,88,0.12)", color: "var(--moss-green)", border: "1.5px solid var(--moss-green)", borderRadius: "20px", padding: "0.3rem 0.8rem", fontSize: "0.78rem", fontWeight: 600, cursor: "pointer" }}>✓ Done</button>
                    <button onClick={() => markTask(task, "missed")} style={{ background: "rgba(211,150,140,0.1)", color: "var(--rosy)", border: "1.5px solid var(--rosy)", borderRadius: "20px", padding: "0.3rem 0.8rem", fontSize: "0.78rem", fontWeight: 600, cursor: "pointer" }}>✗ Miss</button>
                  </>
                )}
              </div>
              <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: "0.2rem" }}>
                <button onClick={() => fireTestNotification(task)} style={{
                  background: "rgba(16,86,102,0.1)", color: "var(--midnight)",
                  border: "1.5px solid var(--midnight)", borderRadius: "20px",
                  padding: "0.3rem 0.7rem", fontSize: "0.72rem", fontWeight: 600,
                  cursor: "pointer", whiteSpace: "nowrap"
                }}>🔔 Test</button>
                <span style={{ fontSize: "0.6rem", color: "var(--text-muted)", textAlign: "center" }}>demo only</span>
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
