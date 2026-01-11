// Mock Flood Alert Data with Real Ganga River Cities
const mockAlerts = [
    {
        id: 1,
        location: 'Varanasi',
        city: 'Varanasi',
        region: 'Uttar Pradesh',
        severity: 'high',
        waterLevel: 72.5,
        threshold: { danger: 71.0, warning: 70.0, safe: 68.0 },
        discharge: 75000,
        rainfall: 145,
        affectedPopulation: 25000,
        timestamp: new Date(Date.now() - 1000 * 60 * 15).toISOString(),
        message: 'CRITICAL: Water level exceeding danger mark. Immediate evacuation recommended.',
        color: '#ef4444'
    },
    {
        id: 2,
        location: 'Patna',
        city: 'Patna',
        region: 'Bihar',
        severity: 'medium',
        waterLevel: 48.8,
        threshold: { danger: 49.0, warning: 48.5, safe: 47.0 },
        discharge: 45000,
        rainfall: 85,
        affectedPopulation: 12000,
        timestamp: new Date(Date.now() - 1000 * 60 * 30).toISOString(),
        message: 'WARNING: Water level approaching warning mark. Prepare for possible evacuation.',
        color: '#f59e0b'
    },
    {
        id: 3,
        location: 'Haridwar',
        city: 'Haridwar',
        region: 'Uttarakhand',
        severity: 'low',
        waterLevel: 293.2,
        threshold: { danger: 295.0, warning: 294.0, safe: 292.0 },
        discharge: 28000,
        rainfall: 35,
        affectedPopulation: 3000,
        timestamp: new Date(Date.now() - 1000 * 60 * 45).toISOString(),
        message: 'ADVISORY: Water levels within safe range. Continue monitoring.',
        color: '#22c55e'
    },
    {
        id: 4,
        location: 'Prayagraj',
        city: 'Prayagraj (Allahabad)',
        region: 'Uttar Pradesh',
        severity: 'medium',
        waterLevel: 84.7,
        threshold: { danger: 85.0, warning: 84.5, safe: 83.0 },
        discharge: 52000,
        rainfall: 92,
        affectedPopulation: 18000,
        timestamp: new Date(Date.now() - 1000 * 60 * 60).toISOString(),
        message: 'WARNING: Water level at warning threshold. Move valuables to higher ground.',
        color: '#f59e0b'
    },
    {
        id: 5,
        location: 'Kanpur',
        city: 'Kanpur',
        region: 'Uttar Pradesh',
        severity: 'high',
        waterLevel: 125.8,
        threshold: { danger: 125.0, warning: 124.0, safe: 122.0 },
        discharge: 68000,
        rainfall: 125,
        affectedPopulation: 32000,
        timestamp: new Date(Date.now() - 1000 * 60 * 20).toISOString(),
        message: 'CRITICAL: Severe flooding expected. Evacuate low-lying areas immediately.',
        color: '#ef4444'
    },
    {
        id: 6,
        location: 'Farakka',
        city: 'Farakka',
        region: 'West Bengal',
        severity: 'low',
        waterLevel: 20.2,
        threshold: { danger: 21.0, warning: 20.5, safe: 19.5 },
        discharge: 31000,
        rainfall: 42,
        affectedPopulation: 5000,
        timestamp: new Date(Date.now() - 1000 * 60 * 90).toISOString(),
        message: 'ADVISORY: Water levels normal. Situation under control.',
        color: '#22c55e'
    },
    {
        id: 7,
        location: 'Rishikesh',
        city: 'Rishikesh',
        region: 'Uttarakhand',
        severity: 'low',
        waterLevel: 340.5,
        threshold: { danger: 345.0, warning: 342.0, safe: 338.0 },
        discharge: 22000,
        rainfall: 28,
        affectedPopulation: 2000,
        timestamp: new Date(Date.now() - 1000 * 60 * 120).toISOString(),
        message: 'ADVISORY: Normal water flow. No immediate threat.',
        color: '#22c55e'
    },
    {
        id: 8,
        location: 'Kolkata',
        city: 'Kolkata (Hooghly)',
        region: 'West Bengal',
        severity: 'medium',
        waterLevel: 6.8,
        threshold: { danger: 7.5, warning: 6.5, safe: 5.5 },
        discharge: 38000,
        rainfall: 75,
        affectedPopulation: 15000,
        timestamp: new Date(Date.now() - 1000 * 60 * 50).toISOString(),
        message: 'WARNING: Rising tide levels. Monitor coastal areas.',
        color: '#f59e0b'
    }
];

let currentFilter = { region: '', severity: '' };
let blinkingInterval = null;

// Initialize dashboard
function initDashboard() {
    updateStats();
    renderAlertCards(mockAlerts);
    renderBlinkingAlerts();
    setupEventListeners();
}

// Update statistics with traffic light colors
function updateStats() {
    const alerts = getFilteredAlerts();
    const totalAlerts = alerts.length;
    const highAlerts = alerts.filter(a => a.severity === 'high').length;
    const mediumAlerts = alerts.filter(a => a.severity === 'medium').length;
    const totalAffected = alerts.reduce((sum, a) => sum + a.affectedPopulation, 0);
    const avgRainfall = alerts.length > 0 ? Math.round(alerts.reduce((sum, a) => sum + a.rainfall, 0) / alerts.length) : 0;

    const statCards = document.querySelectorAll('.stat-card');

    document.getElementById('totalAlerts').textContent = totalAlerts;
    if (highAlerts > 0) {
        statCards[0].style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    } else if (mediumAlerts > 0) {
        statCards[0].style.background = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
    } else {
        statCards[0].style.background = 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)';
    }

    document.getElementById('highAlerts').textContent = highAlerts;
    statCards[1].style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    const highPercentage = totalAlerts > 0 ? (highAlerts / totalAlerts) * 100 : 0;
    document.getElementById('highBar').style.width = `${highPercentage}%`;

    document.getElementById('affectedAreas').textContent = totalAffected.toLocaleString();
    if (totalAffected > 50000) {
        statCards[2].style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    } else if (totalAffected > 20000) {
        statCards[2].style.background = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
    } else {
        statCards[2].style.background = 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)';
    }

    document.getElementById('avgRainfall').textContent = `${avgRainfall} mm`;
    if (avgRainfall > 100) {
        statCards[3].style.background = 'linear-gradient(135deg, #ef4444 0%, #dc2626 100%)';
    } else if (avgRainfall > 50) {
        statCards[3].style.background = 'linear-gradient(135deg, #f59e0b 0%, #d97706 100%)';
    } else {
        statCards[3].style.background = 'linear-gradient(135deg, #22c55e 0%, #16a34a 100%)';
    }
}

// Get filtered alerts
function getFilteredAlerts() {
    return mockAlerts.filter(alert => {
        const regionMatch = !currentFilter.region || alert.region === currentFilter.region;
        const severityMatch = !currentFilter.severity || alert.severity === currentFilter.severity;
        return regionMatch && severityMatch;
    });
}

// Render alert cards
function renderAlertCards(alerts) {
    const grid = document.getElementById('dashboardGrid');
    grid.innerHTML = '';

    if (alerts.length === 0) {
        grid.innerHTML = '<div style="padding: 40px; text-align: center; color: #666;">No alerts match the selected filters.</div>';
        return;
    }

    alerts.forEach(alert => {
        const card = document.createElement('div');
        card.className = `alert-card severity-${alert.severity}`;
        card.style.borderLeftColor = alert.color;
        card.style.borderLeftWidth = '6px';

        card.innerHTML = `
            <div class="alert-header">
                <div class="alert-location">${alert.city}</div>
                <span class="alert-severity-badge" style="background: ${alert.color}; color: white;">
                    ${alert.severity.toUpperCase()}
                </span>
            </div>
            <div class="alert-details">
                <div style="margin-bottom: 10px;">
                    <strong>Region:</strong> ${alert.region}
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>Water Level:</strong> ${alert.waterLevel.toFixed(1)} m (Danger: ${alert.threshold.danger} m)
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>Discharge:</strong> ${alert.discharge.toLocaleString()} m³/s
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>Rainfall:</strong> ${alert.rainfall} mm
                </div>
                <div style="margin-bottom: 10px;">
                    <strong>Affected:</strong> ${alert.affectedPopulation.toLocaleString()} people
                </div>
                <div style="padding: 10px; background: ${alert.color}15; border-radius: 6px; margin-top: 10px; font-size: 13px; color: #333;">
                    ${alert.message}
                </div>
            </div>
        `;

        grid.appendChild(card);
    });
}

// Render blinking traffic lights
function renderBlinkingAlerts() {
    const list = document.getElementById('alertsList');
    list.innerHTML = '';

    // Clear existing blinking interval
    if (blinkingInterval) {
        clearInterval(blinkingInterval);
    }

    const alerts = getFilteredAlerts();

    if (alerts.length === 0) {
        list.innerHTML = '<li style="padding: 20px; text-align: center; color: #999;">Select a region to see alerts</li>';
        return;
    }

    alerts.forEach((alert, index) => {
        const item = document.createElement('li');
        item.className = 'alert-item';
        item.style.padding = '15px';
        item.style.borderBottom = '1px solid #eee';

        // Determine color based on water level vs threshold
        let lightColor = '#22c55e'; // Green (safe)
        let statusText = 'SAFE';

        if (alert.waterLevel >= alert.threshold.danger) {
            lightColor = '#ef4444'; // Red (danger)
            statusText = 'DANGER';
        } else if (alert.waterLevel >= alert.threshold.warning) {
            lightColor = '#f59e0b'; // Orange (warning)
            statusText = 'WARNING';
        }

        item.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center;">
                <div style="flex: 1;">
                    <div style="font-weight: 600; margin-bottom: 5px;">${alert.city}</div>
                    <div style="font-size: 12px; color: #666;">
                        <span style="background: #e3f2fd; color: #1976d2; padding: 2px 8px; border-radius: 10px; font-size: 11px;">
                            ${alert.region}
                        </span>
                        <span style="margin-left: 10px; font-weight: 600; color: ${lightColor};">
                            ${statusText}
                        </span>
                    </div>
                    <div style="font-size: 11px; color: #999; margin-top: 3px;">
                        Level: ${alert.waterLevel.toFixed(1)}m / Danger: ${alert.threshold.danger}m
                    </div>
                </div>
                <div id="blink-light-${index}" style="width: 20px; height: 20px; border-radius: 50%; background: ${lightColor}; box-shadow: 0 0 10px ${lightColor};"></div>
            </div>
        `;

        list.appendChild(item);
    });

    // Start blinking animation
    let isVisible = true;
    blinkingInterval = setInterval(() => {
        alerts.forEach((alert, index) => {
            const light = document.getElementById(`blink-light-${index}`);
            if (light) {
                if (isVisible) {
                    light.style.opacity = '0.3';
                    light.style.boxShadow = 'none';
                } else {
                    light.style.opacity = '1';
                    let lightColor = '#22c55e';
                    if (alert.waterLevel >= alert.threshold.danger) {
                        lightColor = '#ef4444';
                    } else if (alert.waterLevel >= alert.threshold.warning) {
                        lightColor = '#f59e0b';
                    }
                    light.style.boxShadow = `0 0 15px ${lightColor}`;
                }
            }
        });
        isVisible = !isVisible;
    }, 800); // Blink every 800ms
}

// Setup event listeners
function setupEventListeners() {
    document.getElementById('refreshBtn').addEventListener('click', () => {
        updateStats();
        renderAlertCards(getFilteredAlerts());
        renderBlinkingAlerts();
    });

    document.getElementById('regionFilter').addEventListener('change', (e) => {
        currentFilter.region = e.target.value;
        updateStats();
        renderAlertCards(getFilteredAlerts());
        renderBlinkingAlerts();
    });

    document.getElementById('severityFilter').addEventListener('change', (e) => {
        currentFilter.severity = e.target.value;
        updateStats();
        renderAlertCards(getFilteredAlerts());
        renderBlinkingAlerts();
    });
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', initDashboard);