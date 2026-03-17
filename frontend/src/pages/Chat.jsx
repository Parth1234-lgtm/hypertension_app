import { useState, useEffect, useRef } from "react";
import axios from "axios";

export default function Chat({ patientId }) {
  const [messages, setMessages] = useState([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const bottomRef = useRef(null);

  useEffect(() => {
    // load chat history on mount
    axios.get(`http://localhost:8000/chat-history/${patientId}`)
      .then(res => {
        if (res.data.messages.length > 0) {
          setMessages(res.data.messages);
        } else {
          setMessages([{
            role: "agent",
            message: `Hey! How are you doing today? 😊`,
            timestamp: new Date().toISOString()
          }]);
        }
      })
      .catch(() => {
        setMessages([{
          role: "agent",
          message: "Hey! How are you doing today? 😊",
          timestamp: new Date().toISOString()
        }]);
      });
  }, [patientId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  const sendMessage = async () => {
    if (!input.trim() || loading) return;
    const userMsg = { role: "user", message: input, timestamp: new Date().toISOString() };
    setMessages(prev => [...prev, userMsg]);
    setInput("");
    setLoading(true);

    try {
      const res = await axios.post("http://localhost:8000/chat", {
        patient_id: patientId,
        message: input
      });
      setMessages(prev => [...prev, {
        role: "agent",
        message: res.data.reply,
        timestamp: new Date().toISOString()
      }]);
    } catch {
      setMessages(prev => [...prev, {
        role: "agent",
        message: "Sorry, I'm having trouble connecting right now.",
        timestamp: new Date().toISOString()
      }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      height: "calc(100vh - 130px)",
      background: "var(--card-bg)",
      border: "1.5px solid var(--border)",
      borderRadius: "var(--radius)",
      boxShadow: "var(--shadow)",
      overflow: "hidden"
    }}>
      {/* HEADER */}
      <div style={{
        padding: "1.25rem 1.5rem",
        borderBottom: "1.5px solid var(--border)",
        background: "var(--dark-green)",
        display: "flex",
        alignItems: "center",
        gap: "0.75rem"
      }}>
        <div style={{
          width: "36px", height: "36px",
          borderRadius: "50%",
          background: "var(--moss-green)",
          display: "flex", alignItems: "center", justifyContent: "center",
          fontSize: "1rem"
        }}>🌿</div>
        <div>
          <div style={{
            fontFamily: "'DM Serif Display', serif",
            color: "var(--beige)",
            fontSize: "1rem"
          }}>Care Assistant</div>
          <div style={{ fontSize: "0.72rem", color: "rgba(247,244,213,0.6)" }}>
            Your health companion
          </div>
        </div>
      </div>

      {/* MESSAGES */}
      <div style={{
        flex: 1,
        overflowY: "auto",
        padding: "1.5rem",
        display: "flex",
        flexDirection: "column",
        gap: "1rem"
      }}>
        {messages.map((msg, i) => (
          <div key={i} style={{
            display: "flex",
            justifyContent: msg.role === "user" ? "flex-end" : "flex-start",
          }}>
            <div style={{
              maxWidth: "70%",
              padding: "0.75rem 1rem",
              borderRadius: msg.role === "user"
                ? "16px 16px 4px 16px"
                : "16px 16px 16px 4px",
              background: msg.role === "user"
                ? "var(--dark-green)"
                : "var(--beige)",
              color: msg.role === "user" ? "var(--beige)" : "var(--dark-green)",
              border: msg.role === "agent" ? "1.5px solid var(--border)" : "none",
              fontSize: "0.9rem",
              lineHeight: 1.5,
              boxShadow: "0 1px 4px rgba(10,51,35,0.08)"
            }}>
              {msg.message}
            </div>
          </div>
        ))}
        {loading && (
          <div style={{ display: "flex", justifyContent: "flex-start" }}>
            <div style={{
              padding: "0.75rem 1rem",
              borderRadius: "16px 16px 16px 4px",
              background: "var(--beige)",
              border: "1.5px solid var(--border)",
              color: "var(--text-muted)",
              fontSize: "0.85rem"
            }}>
              typing...
            </div>
          </div>
        )}
        <div ref={bottomRef} />
      </div>

      {/* INPUT */}
      <div style={{
        padding: "1rem 1.5rem",
        borderTop: "1.5px solid var(--border)",
        display: "flex",
        gap: "0.75rem",
        background: "var(--card-bg)"
      }}>
        <input
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={e => e.key === "Enter" && sendMessage()}
          placeholder="Type a message..."
          style={{
            flex: 1,
            padding: "0.75rem 1rem",
            borderRadius: "var(--radius-sm)",
            border: "1.5px solid var(--border)",
            background: "var(--beige)",
            color: "var(--dark-green)",
            fontSize: "0.9rem",
            fontFamily: "'DM Sans', sans-serif",
            outline: "none"
          }}
        />
        <button onClick={sendMessage} disabled={loading} style={{
          background: "var(--dark-green)",
          color: "var(--beige)",
          border: "none",
          borderRadius: "var(--radius-sm)",
          padding: "0.75rem 1.25rem",
          cursor: loading ? "not-allowed" : "pointer",
          fontSize: "0.9rem",
          fontWeight: 600,
          fontFamily: "'DM Sans', sans-serif",
          opacity: loading ? 0.6 : 1,
          transition: "all 0.2s"
        }}>
          Send
        </button>
      </div>
    </div>
  );
}
