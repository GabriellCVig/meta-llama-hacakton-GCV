import React, { useState, useEffect } from 'react';
import SymptomSummary from './SymptomSummary';

function Chat() {
  const [sessionId, setSessionId] = useState(null);
  const [conversation, setConversation] = useState([]);
  const [input, setInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [symptomSummary, setSymptomSummary] = useState('');

  useEffect(() => {
    // On mount, start a new session
    async function startSession() {
      try {
        const resp = await fetch('http://localhost:8000/agent-workflow-start', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' }
        });
        if (!resp.ok) {
          throw new Error(`Failed to start session: ${resp.statusText}`);
        }
        const data = await resp.json();
        setSessionId(data.session_id);
        // Just ask the patient what their symptoms are.
        setConversation([
          {
            sender: 'system',
            message: "What are your symptoms?"
          }
        ]);
      } catch (err) {
        console.error('Error starting session:', err);
      }
    }
    startSession();

    // Cleanup on unmount
    return () => {
      if (sessionId) {
        fetch(`http://localhost:8000/agent-workflow-cleanup/${sessionId}`, {
          method: 'POST'
        }).catch(err => console.error('Cleanup error:', err));
      }
    };
  }, []);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim() || !sessionId || isProcessing) return;

    const userMsg = { sender: 'user', message: input };
    setConversation(prev => [...prev, userMsg]);
    setIsProcessing(true);
    try {
      const resp = await fetch('http://localhost:8000/agent-workflow-chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          session_id: sessionId,
          message: input.trim()
        })
      });
      if (!resp.ok) {
        throw new Error(`Server error: ${resp.statusText}`);
      }
      const data = await resp.json();
      if (input.trim().toLowerCase() === "confirm") {
        // If user typed confirm, show backend's triage result in chat.
        const agentResponse = { sender: 'system', message: data.message };
        setConversation(prev => [...prev, agentResponse]);
      } else {
        // Update the live symptom summary on the right.
        setSymptomSummary(data.message);
        // Post the next system question in the chat.
        const nextQuestion = {
          sender: 'system',
          message: "Any symptoms or context you would like to add? If yes, please write them out. If no, then type confirm."
        };
        setConversation(prev => [...prev, nextQuestion]);
      }
    } catch (err) {
      console.error('Chat error:', err);
      setConversation(prev => [
        ...prev,
        { sender: 'system', message: 'Error occurred. Try again.' }
      ]);
    }
    setInput('');
    setIsProcessing(false);
  };

  return (
    <div className="chat-container" style={{ display: 'flex', gap: '1rem' }}>
      {/* Left Column: Chat Conversation */}
      <div className="chat-box" style={{ flex: 2, display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1, maxHeight: '400px', overflowY: 'auto', marginBottom: '1rem' }}>
          {conversation.map((msg, idx) => (
            <div
              key={idx}
              style={{
                display: 'flex',
                justifyContent: msg.sender === 'user' ? 'flex-end' : 'flex-start',
                margin: '0.5rem 0'
              }}
            >
              <div
                style={{
                  padding: '0.8rem',
                  borderRadius: '12px',
                  backgroundColor: msg.sender === 'user' ? '#007bff' : '#e9ecef',
                  color: msg.sender === 'user' ? '#fff' : '#000',
                  maxWidth: '70%'
                }}
              >
                {msg.message}
              </div>
            </div>
          ))}
        </div>
        <form onSubmit={handleSend} style={{ display: 'flex', gap: '0.5rem' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder="Describe your symptoms or type confirm..."
            style={{ flex: 1 }}
            disabled={isProcessing}
          />
          <button type="submit" disabled={isProcessing}>
            Send
          </button>
        </form>
      </div>
      {/* Right Column: Symptom Summary Card */}
      <div className="summary-box" style={{ flex: 1 }}>
        <SymptomSummary summary={symptomSummary} />
      </div>
    </div>
  );
}

export default Chat;