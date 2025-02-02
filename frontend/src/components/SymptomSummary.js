import React from 'react';

function SymptomSummary({ summary }) {
  return (
    <div
      className="symptom-summary"
      style={{
        border: '1px solid #ccc',
        borderRadius: '8px',
        padding: '1rem',
        backgroundColor: '#f8f9fa',
        minHeight: '200px'
      }}
    >
      <h3>Symptom Summary</h3>
      <p>{summary || "No symptoms added yet."}</p>
    </div>
  );
}

export default SymptomSummary;