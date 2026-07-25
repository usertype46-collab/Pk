import React from 'react';
import { BrowserRouter as Router, Routes, Route, Link } from 'react-router-dom';
import RouteEditor from './components/RouteEditor';

function App() {
  const navStyle = {
    padding: '12px 20px',
    backgroundColor: '#2ea44f', // GitHub 綠色按鈕風格
    color: 'white',
    textDecoration: 'none',
    borderRadius: '6px',
    fontWeight: 'bold',
    display: 'inline-flex',
    alignItems: 'center',
    boxShadow: '0 1px 3px rgba(27,31,35,.15)',
    border: '1px solid rgba(27,31,36,.15)'
  };

  return (
    <Router>
      <div style={{ padding: '20px', maxWidth: '1200px', margin: '0 auto' }}>
        <h1 style={{ borderBottom: '2px solid #eaecef', paddingBottom: '10px' }}>🏭 數位雙生工廠控制台</h1>
        
        <nav style={{ display: 'flex', gap: '15px', marginBottom: '30px', flexWrap: 'wrap' }}>
          <Link to="/wait" style={navStyle}>📦 進入 待料.html (Waiting)</Link>
          <Link to="/load" style={navStyle}>🏗️ 進入 上料.html (Loading)</Link>
          <Link to="/unload" style={navStyle}>✅ 進入 下料.html (Unloading)</Link>
        </nav>

        <Routes>
          <Route path="/wait" element={<RouteEditor pageName="waiting" title="📦 待料區設定" />} />
          <Route path="/load" element={<RouteEditor pageName="loading" title="🏗️ 待上料_阿利設定" />} />
          <Route path="/unload" element={<RouteEditor pageName="unloading" title="✅ 下料與完成紀錄設定" />} />
          <Route path="/" element={
            <div style={{ padding: '40px', background: '#f6f8fa', borderRadius: '10px', textAlign: 'center' }}>
              <h2>請選擇上方按鈕進入各站點客製化設定</h2>
              <p style={{ color: '#57606a' }}>您可以動態調整卡片尺寸，並透過拖拉黃色節點即時修改 D3.js 繪製的軌道路徑。</p>
            </div>
          } />
        </Routes>
      </div>
    </Router>
  );
}

export default App;
