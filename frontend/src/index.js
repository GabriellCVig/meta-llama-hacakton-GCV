import React from 'react';
import ReactDOM from 'react-dom/client';
import App from './App';
import './index.css'; // Global styles for the application

// Entry point of the React application.
// Renders the main App component into the root DOM node.
const root = ReactDOM.createRoot(document.getElementById('root'));
root.render(
  <React.StrictMode>
    <App />
  </React.StrictMode>
);
