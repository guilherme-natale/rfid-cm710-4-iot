import React from 'react';
import './App.css';

function App() {
  return (
    <div className="app-container">
      <div className="content">
        <div className="icon">📡</div>
        <h1>RFID Cloud API</h1>
        <p className="version">v2.0.0</p>
        <p className="description">
          Central configuration and device management for RFID IoT devices.
        </p>
        
        <div className="status-badge">
          <span className="dot"></span>
          API Operational
        </div>

        <div className="links">
          <a href="/api/docs" className="link-btn primary">
            API Documentation
          </a>
          <a href="/health" className="link-btn secondary">
            Health Check
          </a>
        </div>

        <div className="info-section">
          <h2>Endpoints</h2>
          <div className="endpoint-list">
            <div className="endpoint">
              <span className="method post">POST</span>
              <span className="path">/api/devices/authenticate</span>
            </div>
            <div className="endpoint">
              <span className="method get">GET</span>
              <span className="path">/api/config</span>
            </div>
            <div className="endpoint">
              <span className="method post">POST</span>
              <span className="path">/api/readings</span>
            </div>
            <div className="endpoint">
              <span className="method post">POST</span>
              <span className="path">/api/admin/devices/register</span>
            </div>
          </div>
        </div>

        <p className="footer">
          Zero secrets on client devices • Cloud as single source of truth
        </p>
      </div>
    </div>
  );
}

export default App;
