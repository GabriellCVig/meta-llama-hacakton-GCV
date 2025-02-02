// File: /Users/gabriellvig/Documents/ER-triage-demo/system/frontend/src/components/Results.js
import React from 'react';

/**
 * Results Component
 * -----------------
 * This component displays the final triage outcome in a clear and user-friendly format.
 * It accepts the following props:
 *  - severity: a number representing the severity rank (e.g., 1–5).
 *  - waitTime: a string representing the estimated wait time or queue position.
 *  - explanation: a string that explains the triage decision.
 *
 * Example usage:
 *   <Results
 *     severity={3}
 *     waitTime="20 minutes"
 *     explanation="Based on your symptoms, we advise you to wait for further evaluation."
 *   />
 */
function Results({ severity, waitTime, explanation }) {
  return (
    <div
      className="results-container"
      style={{
        border: '1px solid #ccc',
        padding: '16px',
        borderRadius: '8px',
        marginTop: '16px',
        backgroundColor: '#f9f9f9'
      }}
    >
      <h2 style={{ marginBottom: '12px' }}>Triage Results</h2>
      <p>
        <strong>Severity Rank:</strong> {severity}
      </p>
      <p>
        <strong>Estimated Wait Time:</strong> {waitTime}
      </p>
      <p>
        <strong>Explanation:</strong> {explanation}
      </p>
    </div>
  );
}

export default Results;