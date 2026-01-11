/**
 * Flood Alert Banner Component
 * floodAllertBanner.jsx - React component for displaying urgent flood alerts
 */

import React, { useState, useEffect, useCallback } from 'react';
import PropTypes from 'prop-types';
import './floodAllertBanner.css';

const FloodAllertBanner = ({ 
  initialAlerts = [],
  autoRefresh = true,
  refreshInterval = 30000,
  apiEndpoint = 'http://localhost:8000/api/flood-alerts/',
  showEvacuationZones = true,
  maxVisibleAlerts = 3,
  onAlertClick,
  onDismiss,
  showSoundControls = true
}) => {
  // State management
  const [alerts, setAlerts] = useState(initialAlerts);
  const [activeAlertIndex, setActiveAlertIndex] = useState(0);
  const [isExpanded, setIsExpanded] = useState(false);
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [soundEnabled, setSoundEnabled] = useState(true);
  const [lastUpdate, setLastUpdate] = useState(new Date());
  const [isVisible, setIsVisible] = useState(true);

  // Mock data for demonstration
  const mockAlerts = [
    {
      id: 1,
      type: 'FLOOD_WARNING',
      severity: 'HIGH',
      title: 'Severe Flood Warning',
      location: 'River Thames, London',
      description: 'River levels are rising rapidly due to heavy rainfall. Immediate action required.',
      rainfall: '85mm',
      waterLevel: '4.2m',
      affectedAreas: ['Westminster', 'Lambeth', 'Southwark'],
      evacuation: true,
      timestamp: new Date(Date.now() - 1800000).toISOString(), // 30 minutes ago
      expires: new Date(Date.now() + 21600000).toISOString(), // 6 hours from now
      source: 'Environment Agency',
      color: '#dc3545',
      icon: '⚠️'
    },
    {
      id: 2,
      type: 'FLOOD_ALERT',
      severity: 'MEDIUM',
      title: 'Flood Alert',
      location: 'Northern Hills Region',
      description: 'Moderate flooding expected in low-lying areas. Stay alert.',
      rainfall: '52mm',
      waterLevel: '2.8m',
      affectedAreas: ['Northern District', 'Hill Valley'],
      evacuation: false,
      timestamp: new Date(Date.now() - 3600000).toISOString(), // 1 hour ago
      expires: new Date(Date.now() + 43200000).toISOString(), // 12 hours from now
      source: 'Met Office',
      color: '#ffc107',
      icon: '⚠️'
    },
    {
      id: 3,
      type: 'FLOOD_ADVICE',
      severity: 'LOW',
      title: 'Flood Advice',
      location: 'Eastern Plains',
      description: 'Minor flooding possible. Monitor local updates.',
      rainfall: '35mm',
      waterLevel: '1.5m',
      affectedAreas: ['East Farmlands'],
      evacuation: false,
      timestamp: new Date(Date.now() - 7200000).toISOString(), // 2 hours ago
      expires: new Date(Date.now() + 86400000).toISOString(), // 24 hours from now
      source: 'Local Council',
      color: '#28a745',
      icon: 'ℹ️'
    }
  ];

  // Fetch alerts from API
  const fetchAlerts = useCallback(async () => {
    if (!apiEndpoint) return;
    
    setIsLoading(true);
    setError(null);
    
    try {
      // For demo, use mock data. Replace with real API call:
      // const response = await fetch(apiEndpoint);
      // const data = await response.json();
      
      // Simulate API delay
      await new Promise(resolve => setTimeout(resolve, 500));
      
      // Use mock data for demonstration
      setAlerts(mockAlerts);
      setLastUpdate(new Date());
      
      // Play alert sound if new high severity alerts
      if (soundEnabled && mockAlerts.some(alert => alert.severity === 'HIGH')) {
        playAlertSound();
      }
      
    } catch (err) {
      console.error('Error fetching flood alerts:', err);
      setError('Failed to load flood alerts. Using last known data.');
      // Fallback to mock data on error
      setAlerts(mockAlerts.slice(0, 1));
    } finally {
      setIsLoading(false);
    }
  }, [apiEndpoint, soundEnabled]);

  // Initialize and set up auto-refresh
  useEffect(() => {
    // Load initial data
    fetchAlerts();
    
    // Set up auto-refresh if enabled
    let intervalId;
    if (autoRefresh && apiEndpoint) {
      intervalId = setInterval(fetchAlerts, refreshInterval);
    }
    
    // Cleanup
    return () => {
      if (intervalId) clearInterval(intervalId);
    };
  }, [fetchAlerts, autoRefresh, refreshInterval, apiEndpoint]);

  // Alert sound management
  const playAlertSound = () => {
    if (!soundEnabled) return;
    
    // Create and play alert sound
    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const oscillator = audioContext.createOscillator();
    const gainNode = audioContext.createGain();
    
    oscillator.connect(gainNode);
    gainNode.connect(audioContext.destination);
    
    oscillator.frequency.setValueAtTime(800, audioContext.currentTime);
    oscillator.frequency.setValueAtTime(600, audioContext.currentTime + 0.1);
    oscillator.frequency.setValueAtTime(800, audioContext.currentTime + 0.2);
    
    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 0.5);
    
    oscillator.start(audioContext.currentTime);
    oscillator.stop(audioContext.currentTime + 0.5);
  };

  // Navigation handlers
  const nextAlert = () => {
    setActiveAlertIndex((prev) => (prev + 1) % alerts.length);
  };

  const prevAlert = () => {
    setActiveAlertIndex((prev) => (prev - 1 + alerts.length) % alerts.length);
  };

  // Format timestamp
  const formatTime = (timestamp) => {
    const date = new Date(timestamp);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    
    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins} minutes ago`;
    if (diffMins < 1440) return `${Math.floor(diffMins / 60)} hours ago`;
    return date.toLocaleDateString();
  };

  // Get severity badge style
  const getSeverityStyle = (severity) => {
    const styles = {
      HIGH: {
        backgroundColor: '#dc3545',
        color: 'white',
        borderColor: '#bd2130'
      },
      MEDIUM: {
        backgroundColor: '#ffc107',
        color: '#212529',
        borderColor: '#d39e00'
      },
      LOW: {
        backgroundColor: '#28a745',
        color: 'white',
        borderColor: '#1e7e34'
      }
    };
    return styles[severity] || styles.LOW;
  };

  // Get alert icon
  const getAlertIcon = (severity) => {
    const icons = {
      HIGH: '🚨',
      MEDIUM: '⚠️',
      LOW: 'ℹ️'
    };
    return icons[severity] || 'ℹ️';
  };

  // Handle alert click
  const handleAlertClick = (alert) => {
    if (onAlertClick) {
      onAlertClick(alert);
    } else {
      // Default behavior: expand to show details
      setIsExpanded(!isExpanded);
    }
  };

  // Handle dismiss
  const handleDismiss = () => {
    if (onDismiss) {
      onDismiss(alerts[activeAlertIndex]);
    }
    setIsVisible(false);
    
    // Auto-show again after 5 minutes if there are high severity alerts
    if (alerts.some(a => a.severity === 'HIGH')) {
      setTimeout(() => setIsVisible(true), 300000);
    }
  };

  // If no alerts or banner dismissed, don't render
  if (alerts.length === 0 || !isVisible) {
    return null;
  }

  const currentAlert = alerts[activeAlertIndex];

  return (
    <div className={`flood-alert-banner ${currentAlert.severity.toLowerCase()}`}>
      {/* Main Banner */}
      <div 
        className="banner-main"
        style={{ borderLeft: `6px solid ${currentAlert.color}` }}
        onClick={() => handleAlertClick(currentAlert)}
        role="button"
        tabIndex={0}
        aria-label={`Flood alert: ${currentAlert.title}. Click for details.`}
      >
        <div className="banner-header">
          <div className="alert-indicator">
            <span className="alert-icon" style={{ fontSize: '24px' }}>
              {getAlertIcon(currentAlert.severity)}
            </span>
            <span className="alert-type">{currentAlert.type.replace('_', ' ')}</span>
          </div>
          
          <div className="banner-controls">
            {showSoundControls && (
              <button 
                className="sound-toggle"
                onClick={(e) => {
                  e.stopPropagation();
                  setSoundEnabled(!soundEnabled);
                }}
                aria-label={soundEnabled ? 'Mute alert sounds' : 'Unmute alert sounds'}
              >
                {soundEnabled ? '🔊' : '🔇'}
              </button>
            )}
            
            <button 
              className="dismiss-btn"
              onClick={(e) => {
                e.stopPropagation();
                handleDismiss();
              }}
              aria-label="Dismiss alert"
            >
              ×
            </button>
          </div>
        </div>

        <div className="banner-content">
          <div className="alert-main-info">
            <h3 className="alert-title">{currentAlert.title}</h3>
            <div className="alert-location">
              <span className="location-icon">📍</span>
              {currentAlert.location}
            </div>
          </div>

          <div className="alert-metrics">
            <div className="metric">
              <span className="metric-label">Rainfall:</span>
              <span className="metric-value">{currentAlert.rainfall}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Water Level:</span>
              <span className="metric-value">{currentAlert.waterLevel}</span>
            </div>
            <div className="metric">
              <span className="metric-label">Updated:</span>
              <span className="metric-value">{formatTime(currentAlert.timestamp)}</span>
            </div>
          </div>

          <div className="severity-indicator">
            <span 
              className="severity-badge"
              style={getSeverityStyle(currentAlert.severity)}
            >
              {currentAlert.severity} SEVERITY
            </span>
            {currentAlert.evacuation && (
              <span className="evacuation-badge">
                🚨 EVACUATION ADVISED
              </span>
            )}
          </div>
        </div>

        {/* Alert Navigation */}
        {alerts.length > 1 && (
          <div className="alert-navigation">
            <button 
              className="nav-btn prev-btn"
              onClick={(e) => {
                e.stopPropagation();
                prevAlert();
              }}
              aria-label="Previous alert"
            >
              ◀
            </button>
            <div className="alert-counter">
              Alert {activeAlertIndex + 1} of {alerts.length}
            </div>
            <button 
              className="nav-btn next-btn"
              onClick={(e) => {
                e.stopPropagation();
                nextAlert();
              }}
              aria-label="Next alert"
            >
              ▶
            </button>
          </div>
        )}
      </div>

      {/* Expanded Details */}
      {isExpanded && (
        <div className="alert-details">
          <div className="details-section">
            <h4>Description</h4>
            <p>{currentAlert.description}</p>
          </div>

          {showEvacuationZones && currentAlert.affectedAreas && (
            <div className="details-section">
              <h4>Affected Areas</h4>
              <div className="affected-areas">
                {currentAlert.affectedAreas.map((area, index) => (
                  <span key={index} className="area-tag">
                    {area}
                  </span>
                ))}
              </div>
            </div>
          )}

          <div className="details-grid">
            <div className="detail-item">
              <span className="detail-label">Source:</span>
              <span className="detail-value">{currentAlert.source}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Issued:</span>
              <span className="detail-value">{formatTime(currentAlert.timestamp)}</span>
            </div>
            <div className="detail-item">
              <span className="detail-label">Expires:</span>
              <span className="detail-value">
                {new Date(currentAlert.expires).toLocaleTimeString([], { 
                  hour: '2-digit', 
                  minute: '2-digit' 
                })}
              </span>
            </div>
          </div>

          {currentAlert.evacuation && (
            <div className="evacuation-notice">
              <div className="evacuation-icon">🚨</div>
              <div className="evacuation-content">
                <h4>IMMEDIATE EVACUATION ADVISORY</h4>
                <p>Move to higher ground immediately. Follow local authority instructions.</p>
                <div className="evacuation-actions">
                  <button className="emergency-btn">
                    🚨 Call Emergency Services
                  </button>
                  <button className="shelter-btn">
                    🏠 Find Nearest Shelter
                  </button>
                </div>
              </div>
            </div>
          )}

          <div className="details-footer">
            <button 
              className="refresh-btn"
              onClick={(e) => {
                e.stopPropagation();
                fetchAlerts();
              }}
              disabled={isLoading}
            >
              {isLoading ? '🔄 Loading...' : '🔄 Refresh Data'}
            </button>
            <div className="last-update">
              Last updated: {lastUpdate.toLocaleTimeString()}
            </div>
          </div>
        </div>
      )}

      {/* Loading State */}
      {isLoading && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <span>Updating flood alerts...</span>
        </div>
      )}

      {/* Error State */}
      {error && (
        <div className="error-message">
          ⚠️ {error}
        </div>
      )}

      {/* Auto-refresh indicator */}
      {autoRefresh && (
        <div className="auto-refresh-indicator">
          <div className="refresh-progress">
            <div 
              className="progress-bar" 
              style={{ 
                animationDuration: `${refreshInterval}ms`,
                animationPlayState: isLoading ? 'paused' : 'running'
              }}
            />
          </div>
          <span className="refresh-text">Auto-refresh in progress</span>
        </div>
      )}
    </div>
  );
};

// PropTypes for type checking
FloodAllertBanner.propTypes = {
  initialAlerts: PropTypes.arrayOf(PropTypes.shape({
    id: PropTypes.oneOfType([PropTypes.string, PropTypes.number]).isRequired,
    type: PropTypes.string.isRequired,
    severity: PropTypes.oneOf(['HIGH', 'MEDIUM', 'LOW']).isRequired,
    title: PropTypes.string.isRequired,
    location: PropTypes.string.isRequired,
    description: PropTypes.string,
    rainfall: PropTypes.string,
    waterLevel: PropTypes.string,
    affectedAreas: PropTypes.arrayOf(PropTypes.string),
    evacuation: PropTypes.bool,
    timestamp: PropTypes.string.isRequired,
    expires: PropTypes.string,
    source: PropTypes.string,
    color: PropTypes.string,
    icon: PropTypes.string
  })),
  autoRefresh: PropTypes.bool,
  refreshInterval: PropTypes.number,
  apiEndpoint: PropTypes.string,
  showEvacuationZones: PropTypes.bool,
  maxVisibleAlerts: PropTypes.number,
  onAlertClick: PropTypes.func,
  onDismiss: PropTypes.func,
  showSoundControls: PropTypes.bool
};

// Default props
FloodAllertBanner.defaultProps = {
  initialAlerts: [],
  autoRefresh: true,
  refreshInterval: 30000,
  apiEndpoint: '',
  showEvacuationZones: true,
  maxVisibleAlerts: 3,
  showSoundControls: true
};

export default FloodAllertBanner;