import React from 'react';
import Chat from './components/Chat';
import './App.css'; // Styles specific to the App component

function App() {
  return (
    <div className="App">
      <header className="App-header">
        <h1>ER Triage Demo</h1>
      </header>
      <main>
        <Chat />
      </main>
    </div>
  );
}

export default App;