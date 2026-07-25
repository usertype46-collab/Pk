import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import SimulatorEditor from './SimulatorEditor';
import WaitingArea from './WaitingArea';
import LoadingArea from './LoadingArea';
import UnloadingArea from './UnloadingArea';

function App() {
  const gitHubBtnStyle = {
    backgroundColor: '#2ea44f', color: '#ffffff', padding: '8px 16px',
    borderRadius: '6px', textDecoration: 'none', fontWeight: '600',
    border: '1px solid rgba(27,31,35,0.15)', display: 'inline-block', margin: '5px'
  };

  return (
    <Router>
      <div style={{ padding: '10px', backgroundColor: '#f6f8fa', borderBottom: '1px solid #d1d5da' }}>
        <nav>
          <Link to="/" style={gitHubBtnStyle}>⚙️ 軌道客製化模擬器</Link>
          <Link to="/wait" style={gitHubBtnStyle}>📦 待料區 (待料.html)</Link>
          <Link to="/load" style={gitHubBtnStyle}>🏗️ 上料區 (上料.html)</Link>
          <Link to="/unload" style={gitHubBtnStyle}>✅ 下料區 (下料.html)</Link>
        </nav>
      </div>
      <Routes>
        <Route path="/" element={<SimulatorEditor />} />
        <Route path="/wait" element={<WaitingArea />} />
        <Route path="/load" element={<LoadingArea />} />
        <Route path="/unload" element={<UnloadingArea />} />
      </Routes>
    </Router>
  );
}
export default App;
