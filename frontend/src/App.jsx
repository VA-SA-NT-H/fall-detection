import React, { useState, useEffect, useRef } from 'react';
import axios from 'axios';
import { Shield, Eye, Settings, RefreshCw, AlertTriangle, Play, Square, Activity, Bell, FileText, Lock, User as UserIcon, LogOut } from 'lucide-react';

const API_BASE = 'http://localhost:8000';

function App() {
  const [token, setToken] = useState(localStorage.getItem('token') || '');
  const [activeTab, setActiveTab] = useState('dashboard');
  const [source, setSource] = useState('0');
  const [isStreaming, setIsStreaming] = useState(false);
  const [status, setStatus] = useState({
    state: 'Normal',
    potential_fall_start: null,
    verification_duration: 3.0,
    last_features: {}
  });

  // Login / Register Form States
  const [isRegistering, setIsRegistering] = useState(false);
  const [usernameInput, setUsernameInput] = useState('');
  const [passwordInput, setPasswordInput] = useState('');
  const [authError, setAuthError] = useState('');

  // Settings States
  const [timerDuration, setTimerDuration] = useState(3.0);
  const [velocityThreshold, setVelocityThreshold] = useState(-0.35);
  const [angleThreshold, setAngleThreshold] = useState(50.0);
  const [phoneNumber, setPhoneNumber] = useState('');
  const [twilioSid, setTwilioSid] = useState('');
  const [twilioToken, setTwilioToken] = useState('');
  const [twilioPhone, setTwilioPhone] = useState('');
  const [settingsMessage, setSettingsMessage] = useState('');

  const [logs, setLogs] = useState([]);
  const [events, setEvents] = useState([]);
  const [selectedEvent, setSelectedEvent] = useState(null);
  const statusInterval = useRef(null);

  // Setup Axios defaults with Bearer token
  useEffect(() => {
    if (token) {
      axios.defaults.headers.common['Authorization'] = `Bearer ${token}`;
      localStorage.setItem('token', token);
      fetchUserProfile();
    } else {
      delete axios.defaults.headers.common['Authorization'];
      localStorage.removeItem('token');
    }
  }, [token]);

  const fetchUserProfile = async () => {
    try {
      const response = await axios.get(`${API_BASE}/api/auth/me`);
      const user = response.data;
      setPhoneNumber(user.phone_number || '');
      setTwilioSid(user.twilio_sid || '');
      setTwilioToken(user.twilio_token || '');
      setTwilioPhone(user.twilio_phone || '');
    } catch (e) {
      // If unauthorized, clear token
      if (e.response && e.response.status === 401) {
        setToken('');
      }
    }
  };

  const fetchEvents = async () => {
    if (!token) return;
    try {
      const response = await axios.get(`${API_BASE}/api/events`);
      setEvents(response.data);
    } catch (e) {
      console.error(e);
    }
  };

  const fetchStatus = async () => {
    if (!token) return;
    try {
      const response = await axios.get(`${API_BASE}/api/status`);
      const newStatus = response.data;
      
      if (newStatus.state !== status.state) {
        const timeStr = new Date().toLocaleTimeString();
        let logMsg = `System status changed to: ${newStatus.state}`;
        if (newStatus.state === 'Fall Detected') {
          logMsg = `⚠️ CRITICAL: Fall detected! Caregiver notified.`;
          playAlertSound();
        } else if (newStatus.state === 'Potential Fall') {
          logMsg = `⏳ Potential fall detected. Monitoring for recovery...`;
        } else if (newStatus.state === 'Normal' && status.state !== 'Normal') {
          logMsg = `✅ Recovery verified. State reset to normal.`;
        }
        
        setLogs(prev => [{ time: timeStr, text: logMsg, type: newStatus.state }, ...prev]);
      }
      
      setStatus(newStatus);
    } catch (error) {
      console.error('Error fetching status:', error);
    }
  };

  // Poll status endpoint when streaming is active
  useEffect(() => {
    if (isStreaming && token) {
      statusInterval.current = setInterval(fetchStatus, 300);
    } else {
      clearInterval(statusInterval.current);
    }
    return () => clearInterval(statusInterval.current);
  }, [isStreaming, token]);

  // Fetch events on active changes
  useEffect(() => {
    if (token) {
      fetchEvents();
    }
  }, [status.state, activeTab, token]);

  // Audio effect context for alert
  const audioContextRef = useRef(null);
  const playAlertSound = () => {
    try {
      if (!audioContextRef.current) {
        audioContextRef.current = new (window.AudioContext || window.webkitAudioContext)();
      }
      const ctx = audioContextRef.current;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      
      osc.type = 'sawtooth';
      osc.frequency.setValueAtTime(880, ctx.currentTime);
      gain.gain.setValueAtTime(0.1, ctx.currentTime);
      
      osc.connect(gain);
      gain.connect(ctx.destination);
      osc.start();
      setTimeout(() => osc.stop(), 500);
    } catch (e) {
      console.warn("Could not play audio alert:", e);
    }
  };

  const handleStartStream = () => {
    setIsStreaming(true);
    setLogs(prev => [
      { time: new Date().toLocaleTimeString(), text: `Started video feed from source: ${source}`, type: 'Normal' },
      ...prev
    ]);
  };

  const handleStopStream = async () => {
    setIsStreaming(false);
    try {
      await axios.post(`${API_BASE}/api/stop`);
    } catch (e) {
      console.error(e);
    }
  };

  const handleReset = async () => {
    try {
      await axios.post(`${API_BASE}/api/reset`);
      fetchStatus();
    } catch (e) {
      console.error(e);
    }
  };

  const handleAuthSubmit = async (e) => {
    e.preventDefault();
    setAuthError('');
    const url = isRegistering ? `${API_BASE}/api/auth/register` : `${API_BASE}/api/auth/login`;
    
    try {
      const response = await axios.post(url, {
        username: usernameInput,
        password: passwordInput
      });
      
      if (isRegistering) {
        setIsRegistering(false);
        setSettingsMessage('Registration successful! Please login.');
        setTimeout(() => setSettingsMessage(''), 3000);
      } else {
        setToken(response.data.access_token);
      }
      
      setUsernameInput('');
      setPasswordInput('');
    } catch (err) {
      setAuthError(err.response?.data?.detail || 'Authentication failed. Please try again.');
    }
  };

  const handleSaveSettings = async (e) => {
    e.preventDefault();
    try {
      await axios.post(`${API_BASE}/api/auth/settings`, {
        phone_number: phoneNumber,
        twilio_sid: twilioSid,
        twilio_token: twilioToken,
        twilio_phone: twilioPhone
      });
      setSettingsMessage('Sensitivities and Caregiver alert contacts saved successfully!');
      setTimeout(() => setSettingsMessage(''), 3000);
    } catch (err) {
      console.error(err);
      setSettingsMessage('Failed to save configurations.');
    }
  };

  const handleLogout = () => {
    setToken('');
    setIsStreaming(false);
    setLogs([]);
  };

  const features = status.last_features || {};

  // RENDER LOGIN SCREEN IF NOT AUTHENTICATED
  if (!token) {
    return (
      <div style={{
        display: 'flex',
        alignItems: 'center',
        justifyContent: 'center',
        minHeight: '100vh',
        backgroundColor: 'var(--bg-primary)',
        padding: '20px'
      }}>
        <div className="glass-card" style={{ width: '100%', maxWidth: '420px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div style={{ textAlign: 'center' }}>
            <div className="logo-icon" style={{ margin: '0 auto 16px auto', width: '48px', height: '48px' }}>
              <Shield size={24} />
            </div>
            <h2 style={{ fontSize: '1.5rem', fontWeight: 700 }}>{isRegistering ? 'Register Caregiver' : 'Caregiver Login'}</h2>
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem', marginTop: '6px' }}>
              {isRegistering ? 'Create a secure dashboard operator account.' : 'Sign in to access real-time fall detection monitoring.'}
            </p>
          </div>

          <form onSubmit={handleAuthSubmit} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Username</label>
              <div style={{ position: 'relative' }}>
                <UserIcon size={16} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)' }} />
                <input 
                  type="text" 
                  className="input-field" 
                  style={{ paddingLeft: '40px', width: '100%' }}
                  placeholder="Enter username" 
                  value={usernameInput}
                  onChange={(e) => setUsernameInput(e.target.value)}
                  required
                />
              </div>
            </div>

            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Password</label>
              <div style={{ position: 'relative' }}>
                <Lock size={16} style={{ position: 'absolute', left: '12px', top: '12px', color: 'var(--text-muted)' }} />
                <input 
                  type="password" 
                  className="input-field" 
                  style={{ paddingLeft: '40px', width: '100%' }}
                  placeholder="Enter password" 
                  value={passwordInput}
                  onChange={(e) => setPasswordInput(e.target.value)}
                  required
                />
              </div>
            </div>

            {authError && (
              <div style={{ color: 'var(--accent-danger)', fontSize: '0.85rem', fontWeight: 500 }}>
                {authError}
              </div>
            )}
            
            {settingsMessage && (
              <div style={{ color: 'var(--accent-success)', fontSize: '0.85rem', fontWeight: 500 }}>
                {settingsMessage}
              </div>
            )}

            <button type="submit" className="btn btn-primary" style={{ width: '100%', marginTop: '8px', padding: '12px' }}>
              {isRegistering ? 'Register Account' : 'Sign In'}
            </button>
          </form>

          <div style={{ textAlign: 'center', fontSize: '0.9rem' }}>
            <span style={{ color: 'var(--text-secondary)' }}>
              {isRegistering ? 'Already have an account? ' : 'First time deploying? '}
            </span>
            <span 
              style={{ color: 'var(--accent-primary)', cursor: 'pointer', fontWeight: 500 }}
              onClick={() => {
                setIsRegistering(!isRegistering);
                setAuthError('');
              }}
            >
              {isRegistering ? 'Login here' : 'Register Operator'}
            </span>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="dashboard-container">
      {/* Sidebar Navigation */}
      <aside className="sidebar">
        <div>
          <div className="logo-container">
            <div className="logo-icon">
              <Shield size={20} />
            </div>
            <div className="logo-text">Fall Detection System</div>
          </div>
          
          <nav>
            <ul className="nav-links">
              <li>
                <div 
                  className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
                  onClick={() => setActiveTab('dashboard')}
                >
                  <Activity size={18} />
                  <span>Dashboard</span>
                </div>
              </li>
              <li>
                <div 
                  className={`nav-item ${activeTab === 'logs' ? 'active' : ''}`}
                  onClick={() => setActiveTab('logs')}
                >
                  <FileText size={18} />
                  <span>Incident Logs</span>
                </div>
              </li>
              <li>
                <div 
                  className={`nav-item ${activeTab === 'settings' ? 'active' : ''}`}
                  onClick={() => setActiveTab('settings')}
                >
                  <Settings size={18} />
                  <span>Settings</span>
                </div>
              </li>
            </ul>
          </nav>
        </div>
        
        <div style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
          <div 
            className="nav-item" 
            onClick={handleLogout}
            style={{ color: 'var(--accent-danger)', background: 'rgba(239, 68, 68, 0.05)' }}
          >
            <LogOut size={18} />
            <span>Sign Out</span>
          </div>
          
          <div style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
            v1.0.0 (Phase 4 Ready)
          </div>
        </div>
      </aside>

      {/* Main Content Area */}
      <main className="main-content">
        <header className="header">
          <div>
            <h1>
              {activeTab === 'dashboard' && 'Real-Time Monitoring'}
              {activeTab === 'logs' && 'Incident Logs'}
              {activeTab === 'settings' && 'System Configuration'}
            </h1>
            <p style={{ color: 'var(--text-secondary)', marginTop: '4px' }}>
              {activeTab === 'dashboard' && 'Live AI-powered human pose estimation & fall risk detection.'}
              {activeTab === 'logs' && 'Historical records of all verified fall events and video recordings.'}
              {activeTab === 'settings' && 'Fine-tune fall detection sensitivities, timings, and SMS alert contacts.'}
            </p>
          </div>
          
          <div className="system-status-indicator">
            <div className={`status-dot ${isStreaming ? 'pulse' : ''}`} />
            <span>{isStreaming ? 'System Active' : 'System Paused'}</span>
          </div>
        </header>

        {/* Tab 1: Dashboard View */}
        {activeTab === 'dashboard' && (
          <div className="dashboard-grid">
            <div className="glass-card video-card">
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h2 style={{ fontSize: '1.2rem', fontWeight: 600 }}>Live Feed</h2>
                <span style={{ fontSize: '0.85rem', background: 'rgba(255,255,255,0.05)', padding: '4px 8px', borderRadius: '4px' }}>
                  Camera Source: {source}
                </span>
              </div>

              <div className="video-container">
                {isStreaming ? (
                  <img
                    src={`${API_BASE}/api/stream?source=${encodeURIComponent(source)}`}
                    alt="Live Stream Feed"
                    className="video-feed"
                    onError={() => setIsStreaming(false)}
                  />
                ) : (
                  <div className="video-placeholder">
                    <Eye size={48} />
                    <p>Video feed is currently disabled</p>
                  </div>
                )}
              </div>

              <div className="control-row">
                <input
                  type="text"
                  className="input-field"
                  placeholder="Camera index (e.g. 0) or path to mp4 file"
                  value={source}
                  onChange={(e) => setSource(e.target.value)}
                  disabled={isStreaming}
                />
                
                {!isStreaming ? (
                  <button className="btn btn-primary" onClick={handleStartStream} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Play size={16} /> Start Feed
                  </button>
                ) : (
                  <button className="btn btn-danger" onClick={handleStopStream} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                    <Square size={16} /> Stop Feed
                  </button>
                )}
                
                <button className="btn btn-secondary" onClick={handleReset} style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                  <RefreshCw size={16} /> Reset State
                </button>
              </div>
            </div>

            <div className="info-column">
              <div className={`alert-box ${status.state === 'Normal' ? 'Normal' : status.state === 'Potential Fall' ? 'Potential' : 'Fall'}`}>
                <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
                  {status.state !== 'Normal' && <AlertTriangle size={24} />}
                  <span>
                    {status.state === 'Normal' && 'SYSTEM STATUS: SAFE'}
                    {status.state === 'Potential Fall' && `POTENTIAL FALL: VERIFYING RECOVERY (${(status.time_to_alert || 0).toFixed(1)}s)`}
                    {status.state === 'Fall Detected' && '🚨 WARNING: FALL DETECTED'}
                  </span>
                </div>
              </div>

              <div className="glass-card">
                <h3 style={{ fontSize: '1.1rem', fontWeight: 600, marginBottom: '16px' }}>Feature Extraction Engine</h3>
                <div className="features-grid">
                  <div className="feature-item">
                    <div className="feature-label">Pose Confidence</div>
                    <div className="feature-value" style={{ color: (features.confidence || 0) > 0.5 ? 'var(--accent-success)' : 'var(--text-secondary)' }}>
                      {((features.confidence || 0) * 100).toFixed(0)}%
                    </div>
                  </div>

                  <div className="feature-item">
                    <div className="feature-label">Body Angle</div>
                    <div className="feature-value">
                      {(features.body_angle || 0).toFixed(1)}°
                    </div>
                  </div>

                  <div className="feature-item">
                    <div className="feature-label">Aspect Ratio</div>
                    <div className="feature-value">
                      {(features.aspect_ratio || 0).toFixed(2)}
                    </div>
                  </div>

                  <div className="feature-item">
                    <div className="feature-label">Velocity</div>
                    <div className="feature-value" style={{ color: (features.velocity || 0) < -0.3 ? 'var(--accent-danger)' : 'var(--text-primary)' }}>
                      {(features.velocity || 0).toFixed(2)}
                    </div>
                  </div>
                </div>
              </div>

              <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', height: '100%', minHeight: '200px' }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '16px' }}>
                  <Bell size={18} style={{ color: 'var(--accent-primary)' }} />
                  <h3 style={{ fontSize: '1.1rem', fontWeight: 600 }}>System Notifications</h3>
                </div>
                
                <div className="event-logs">
                  {logs.length === 0 ? (
                    <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '24px 0' }}>
                      No events registered.
                    </div>
                  ) : (
                    logs.map((log, idx) => (
                      <div key={idx} className={`log-item ${log.type === 'Fall Detected' ? 'fall' : ''}`}>
                        <span>{log.text}</span>
                        <span className="log-time">{log.time}</span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* Tab 2: Incident Logs View */}
        {activeTab === 'logs' && (
          <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '8px', marginBottom: '8px' }}>
              <Play size={18} style={{ color: 'var(--accent-danger)' }} />
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Recorded Fall Video Clips</h2>
            </div>
            
            <div style={{ display: 'flex', flexDirection: 'column', gap: '12px' }}>
              {events.length === 0 ? (
                <div style={{ color: 'var(--text-muted)', textAlign: 'center', padding: '48px 0' }}>
                  No recorded incidents found in backend folder.
                </div>
              ) : (
                events.map((evt, idx) => (
                  <div key={idx} className="event-item" onClick={() => setSelectedEvent(evt.filename)}>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontWeight: 600 }}>{evt.filename}</span>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>Created: {evt.created_at}</span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '16px' }}>
                      <span style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
                        {(evt.size / (1024 * 1024)).toFixed(2)} MB
                      </span>
                      <button className="btn btn-primary" style={{ padding: '6px 12px', fontSize: '0.85rem' }}>
                        Play Clip
                      </button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </div>
        )}

        {/* Tab 3: Settings View */}
        {activeTab === 'settings' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '24px' }}>
            {/* Fall Sensitivity Constants */}
            <div className="glass-card">
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '20px' }}>Sensitivities & Timers</h2>
              
              <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
                    Fall Verification Timer (Seconds): {timerDuration}s
                  </label>
                  <input 
                    type="range" 
                    min="1" 
                    max="10" 
                    step="0.5"
                    style={{ width: '100%' }}
                    value={timerDuration} 
                    onChange={(e) => setTimerDuration(parseFloat(e.target.value))} 
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
                    Downward Velocity Threshold: {velocityThreshold} unit/s
                  </label>
                  <input 
                    type="range" 
                    min="-1.5" 
                    max="-0.1" 
                    step="0.05"
                    style={{ width: '100%' }}
                    value={velocityThreshold} 
                    onChange={(e) => setVelocityThreshold(parseFloat(e.target.value))} 
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
                  <label style={{ fontSize: '0.9rem', fontWeight: 500, color: 'var(--text-secondary)' }}>
                    Body Orientation Angle Threshold: {angleThreshold}°
                  </label>
                  <input 
                    type="range" 
                    min="30" 
                    max="80" 
                    step="1"
                    style={{ width: '100%' }}
                    value={angleThreshold} 
                    onChange={(e) => setAngleThreshold(parseInt(e.target.value))} 
                  />
                </div>
              </div>
            </div>

            {/* Caregiver SMS Alerts Configuration */}
            <div className="glass-card">
              <h2 style={{ fontSize: '1.25rem', fontWeight: 600, marginBottom: '20px' }}>Mobile SMS Alerting (Twilio)</h2>
              
              <form onSubmit={handleSaveSettings} style={{ display: 'flex', flexDirection: 'column', gap: '16px' }}>
                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Caregiver Phone Number</label>
                  <input 
                    type="text" 
                    className="input-field" 
                    placeholder="e.g. +1234567890" 
                    value={phoneNumber}
                    onChange={(e) => setPhoneNumber(e.target.value)}
                    required
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Twilio Account SID</label>
                  <input 
                    type="text" 
                    className="input-field" 
                    placeholder="ACxxxxxxxxxxxxxxxxxxxxxxxx" 
                    value={twilioSid}
                    onChange={(e) => setTwilioSid(e.target.value)}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Twilio Auth Token</label>
                  <input 
                    type="password" 
                    className="input-field" 
                    placeholder="Enter Auth Token" 
                    value={twilioToken}
                    onChange={(e) => setTwilioToken(e.target.value)}
                  />
                </div>

                <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                  <label style={{ fontSize: '0.85rem', color: 'var(--text-secondary)' }}>Twilio From Phone Number</label>
                  <input 
                    type="text" 
                    className="input-field" 
                    placeholder="e.g. +18885551234" 
                    value={twilioPhone}
                    onChange={(e) => setTwilioPhone(e.target.value)}
                  />
                </div>

                {settingsMessage && (
                  <div style={{ color: 'var(--accent-success)', fontSize: '0.9rem', fontWeight: 500 }}>
                    {settingsMessage}
                  </div>
                )}

                <button type="submit" className="btn btn-primary" style={{ marginTop: '8px', alignSelf: 'flex-start' }}>
                  Save Configurations
                </button>
              </form>
            </div>
          </div>
        )}
      </main>

      {/* Video Playback Modal */}
      {selectedEvent && (
        <div className="modal-overlay" onClick={() => setSelectedEvent(null)}>
          <div className="modal-content" onClick={(e) => e.stopPropagation()}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h3 style={{ fontSize: '1.25rem', fontWeight: 600 }}>Event Video Playback</h3>
              <button className="btn btn-secondary" onClick={() => setSelectedEvent(null)} style={{ padding: '6px 12px' }}>
                Close
              </button>
            </div>
            <video
              src={`${API_BASE}/api/events/${selectedEvent}`}
              controls
              autoPlay
              style={{ width: '100%', borderRadius: '8px', border: '1px solid var(--border-color)' }}
            />
            <p style={{ color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
              File: {selectedEvent}
            </p>
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
