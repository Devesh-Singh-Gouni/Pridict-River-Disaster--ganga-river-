# flood_service.py
import logging
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime, timedelta
import requests
from django.conf import settings
from django.utils import timezone
import math

logger = logging.getLogger(__name__)

try:
    from django.contrib.gis.geos import Point
    from django.contrib.gis.measure import Distance
except (ImportError, Exception) as e:
    logger.warning(f"GDAL/GIS libraries not available: {e}. GIS features will be disabled.")
    Point = None
    Distance = None


class FloodRiskService:
    """
    Core flood risk assessment service for Ganga river basin
    Integrates multiple data sources for comprehensive flood monitoring
    """
    
    def __init__(self):
        # Configuration
        self.warning_threshold_m3s = 50000  # m³/s for Orange alert
        self.danger_threshold_m3s = 75000   # m³/s for Red alert
        self.radius_km = 50  # Radius for nearby river gauge search
        
        # API endpoints (configurable via settings)
        self.open_meteo_url = "https://flood-api.open-meteo.com/v1/flood"
        self.gdacs_url = "https://www.gdacs.org/gdacsapi/api/events/geteventlist"
        self.hydroshare_url = "https://www.hydroshare.org/hsapi/resource/"
        
        # Cache for API responses
        self._cache = {}
        self._cache_timeout = 300  # 5 minutes
        
    # ===============================
    # CORE FLOOD RISK ASSESSMENT
    # ===============================
    
    def get_flood_forecast(self, latitude: float, longitude: float) -> Optional[Dict]:
        """
        Get comprehensive flood forecast for a specific location
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            
        Returns:
            Dictionary with flood forecast data or None if failed
        """
        location_key = f"{latitude:.4f},{longitude:.4f}"
        
        # Check cache first
        if location_key in self._cache:
            cached_data, cached_time = self._cache[location_key]
            if (timezone.now() - cached_time).seconds < self._cache_timeout:
                logger.debug(f"Using cached forecast for {location_key}")
                return cached_data
        
        # Check if we should use mock data (if API key is missing or Mock mode is on)
        use_mock = settings.FLOOD_ALERT_SETTINGS.get('MOCK_API', False) or \
                   not settings.FLOOD_ALERT_SETTINGS.get('API_KEY')
                   
        if use_mock:
            logger.info(f"Using MOCK flood data for {location_key}")
            mock_data = self._get_mock_forecast(latitude, longitude)
            self._cache[location_key] = (mock_data, timezone.now())
            return mock_data
        
        try:
            # Primary: Open-Meteo Flood API
            forecast_data = self._get_open_meteo_forecast(latitude, longitude)
            
            if forecast_data:
                # Enhance with local river gauge data
                enhanced_data = self._enhance_with_local_gauges(forecast_data, latitude, longitude)
                
                # Add risk assessment
                enhanced_data['risk_assessment'] = self._assess_flood_risk(enhanced_data)
                
                # Cache the result
                self._cache[location_key] = (enhanced_data, timezone.now())
                return enhanced_data
            
            # Fallback: Other data sources
            logger.warning(f"Primary API failed for {location_key}, trying fallbacks")
            return self._get_fallback_forecast(latitude, longitude)
            
        except Exception as e:
            logger.error(f"Error getting flood forecast for {location_key}: {str(e)}")
            return None

    def _get_mock_forecast(self, latitude: float, longitude: float) -> Dict:
        """Generate realistic mock flood data for demonstrations"""
        import random
        
        # Simulate varying risk levels based on location or random chance
        # For demo purposes, we'll randomize it slightly but keep it consistent for short periods
        
        current_time = timezone.now()
        
        # Generate a sine wave like discharge pattern
        base_discharge = 30000
        variation = 40000 * math.sin(current_time.hour / 4) # oscillate through day
        random_noise = random.randint(-5000, 5000)
        
        current_discharge = max(1000, base_discharge + variation + random_noise)
        
        # Create daily forecast (7 days)
        daily_discharge = []
        daily_time = []
        
        for i in range(7):
            day_time = current_time + timedelta(days=i)
            day_discharge = max(1000, base_discharge + (40000 * math.sin((current_time.hour + i*24) / 4)))
            daily_discharge.append(day_discharge)
            daily_time.append(day_time.isoformat())
            
        # Determine mock risk assessment
        forecast_data = {
            'latitude': latitude,
            'longitude': longitude,
            'elevation': 250,
            'timezone': 'UTC',
            'generationtime_ms': 15.5,
            'source': 'MOCK_DATA_GENERATOR',
            'timestamp': current_time.isoformat(),
            'daily': {
                'time': daily_time,
                'river_discharge': daily_discharge,
                'discharge_mean': [d * 0.9 for d in daily_discharge],
                'discharge_max': [d * 1.1 for d in daily_discharge],
            },
            'mock': True
        }
        
        # Add risk assessment
        forecast_data['risk_assessment'] = self._assess_flood_risk(forecast_data)
        
        return forecast_data

    # ===============================
    # DATA SOURCE INTEGRATION
    # ===============================
    
    def _get_open_meteo_forecast(self, latitude: float, longitude: float) -> Optional[Dict]:
        """Get flood forecast from Open-Meteo API"""
        try:
            params = {
                'latitude': latitude,
                'longitude': longitude,
                'daily': 'river_discharge,discharge_mean,discharge_max',
                'timezone': 'auto',
                'forecast_days': 7,
                'past_days': 2,
                'models': 'seamless'
            }
            
            response = requests.get(
                self.open_meteo_url,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse and structure the data
                structured_data = {
                    'latitude': data.get('latitude', latitude),
                    'longitude': data.get('longitude', longitude),
                    'elevation': data.get('elevation'),
                    'timezone': data.get('timezone'),
                    'generationtime_ms': data.get('generationtime_ms'),
                    'source': 'open-meteo',
                    'timestamp': timezone.now().isoformat(),
                }
                
                # Daily data
                if 'daily' in data:
                    daily_data = data['daily']
                    structured_data['daily'] = {
                        'time': daily_data.get('time', []),
                        'river_discharge': daily_data.get('river_discharge', []),
                        'discharge_mean': daily_data.get('discharge_mean', []),
                        'discharge_max': daily_data.get('discharge_max', []),
                    }
                
                # Hourly data if available
                if 'hourly' in data:
                    hourly_data = data['hourly']
                    structured_data['hourly'] = {
                        'time': hourly_data.get('time', []),
                        'river_discharge': hourly_data.get('river_discharge', []),
                    }
                
                logger.info(f"Successfully retrieved Open-Meteo forecast for {latitude},{longitude}")
                return structured_data
                
        except requests.exceptions.Timeout:
            logger.error(f"Open-Meteo API timeout for {latitude},{longitude}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Open-Meteo API error: {str(e)}")
        except Exception as e:
            logger.error(f"Error processing Open-Meteo response: {str(e)}")
        
        return None
    
    def get_gdacs_alerts(self, latitude: float, longitude: float) -> Optional[str]:
        """
        Get flood alerts from GDACS (Global Disaster Alert and Coordination System)
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            
        Returns:
            Alert level or None if no alerts
        """
        try:
            params = {
                'eventtype': 'FL',
                'limit': 10,
                'fromdate': (timezone.now() - timedelta(days=30)).strftime('%Y-%m-%d'),
            }
            
            response = requests.get(
                self.gdacs_url,
                params=params,
                timeout=8
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Check for alerts near the location
                for event in data.get('features', []):
                    properties = event.get('properties', {})
                    
                    # Check if it's a flood event
                    if properties.get('eventtype') == 'FL':
                        event_location = event.get('geometry', {}).get('coordinates', [])
                        if event_location:
                            event_lat, event_lon = event_location[1], event_location[0]
                            
                            # Calculate distance
                            distance = self._calculate_distance(
                                latitude, longitude,
                                event_lat, event_lon
                            )
                            
                            # If within 100km, return alert level
                            if distance <= 100:  # 100km radius
                                alert_level = properties.get('alertlevel', '').upper()
                                if alert_level in ['RED', 'ORANGE', 'GREEN']:
                                    logger.info(f"GDACS alert found: {alert_level} at {distance:.1f}km")
                                    return alert_level
                
                logger.debug(f"No GDACS alerts near {latitude},{longitude}")
                return None
                
        except Exception as e:
            logger.error(f"Error getting GDACS alerts: {str(e)}")
            return None
    
    def _enhance_with_local_gauges(self, forecast_data: Dict, lat: float, lon: float) -> Dict:
        """Enhance forecast with data from nearby river gauges"""
        try:
            # Import here to avoid circular imports
            from ..models import RiverGauge
            
            # Find nearby active river gauges
            if Point is None:
                logger.warning("GIS features disabled (no GDAL). Cannot find nearby gauges.")
                return forecast_data

            location_point = Point(lon, lat, srid=4326)
            nearby_gauges = RiverGauge.objects.filter(
                is_active=True,
                location__distance_lte=(location_point, Distance(km=self.radius_km))
            )[:5]  # Limit to 5 nearest gauges
            
            if nearby_gauges:
                gauge_data = []
                for gauge in nearby_gauges:
                    gauge_info = {
                        'name': gauge.name,
                        'station_code': gauge.station_code,
                        'distance_km': location_point.distance(gauge.location) * 111,  # Approximate km
                        'current_level': gauge.current_level,
                        'warning_level': gauge.warning_level,
                        'danger_level': gauge.danger_level,
                        'last_updated': gauge.last_updated.isoformat() if gauge.last_updated else None,
                        'river_name': gauge.river_name,
                    }
                    gauge_data.append(gauge_info)
                
                forecast_data['nearby_gauges'] = gauge_data
                
                # Calculate weighted average based on distance
                if gauge_data:
                    forecast_data['local_discharge'] = self._calculate_weighted_discharge(
                        forecast_data, gauge_data
                    )
            
            return forecast_data
            
        except Exception as e:
            logger.error(f"Error enhancing with local gauges: {str(e)}")
            return forecast_data
    
    # ===============================
    # FALLBACK & BACKUP METHODS
    # ===============================
    
    def _get_fallback_forecast(self, latitude: float, longitude: float) -> Optional[Dict]:
        """Get forecast from backup sources when primary fails"""
        # Try GDACS first
        gdacs_alert = self.get_gdacs_alerts(latitude, longitude)
        
        if gdacs_alert:
            return {
                'latitude': latitude,
                'longitude': longitude,
                'source': 'gdacs',
                'timestamp': timezone.now().isoformat(),
                'alert_level': gdacs_alert,
                'fallback': True,
            }
        
        # Try HydroShare if configured
        if hasattr(settings, 'HYDROSHARE_API_KEY'):
            try:
                hydro_data = self._get_hydroshare_data(latitude, longitude)
                if hydro_data:
                    return hydro_data
            except Exception as e:
                logger.error(f"HydroShare fallback failed: {str(e)}")
        
        # Return minimal data structure
        return {
            'latitude': latitude,
            'longitude': longitude,
            'source': 'fallback',
            'timestamp': timezone.now().isoformat(),
            'alert_level': 'GREEN',
            'fallback': True,
            'daily': {
                'river_discharge': [0],
                'time': [timezone.now().isoformat()]
            }
        }
    
    def _get_hydroshare_data(self, latitude: float, longitude: float) -> Optional[Dict]:
        """Get hydrological data from HydroShare (requires API key)"""
        try:
            # This is a simplified example - adjust based on HydroShare API
            headers = {
                'Authorization': f'Bearer {settings.HYDROSHARE_API_KEY}'
            }
            
            # Search for resources near location
            search_params = {
                'lat': latitude,
                'lon': longitude,
                'distance': 50,  # km
                'type': 'ModelInstanceResource'
            }
            
            response = requests.get(
                f"{self.hydroshare_url}",
                params=search_params,
                headers=headers,
                timeout=10
            )
            
            if response.status_code == 200:
                resources = response.json().get('results', [])
                if resources:
                    # Use the first resource
                    resource_id = resources[0].get('resource_id')
                    
                    # Get resource data
                    resource_response = requests.get(
                        f"{self.hydroshare_url}{resource_id}/",
                        headers=headers,
                        timeout=10
                    )
                    
                    if resource_response.status_code == 200:
                        resource_data = resource_response.json()
                        # Parse and return relevant data
                        return {
                            'latitude': latitude,
                            'longitude': longitude,
                            'source': 'hydroshare',
                            'resource_id': resource_id,
                            'resource_title': resource_data.get('resource_title'),
                            'timestamp': timezone.now().isoformat(),
                        }
                        
        except Exception as e:
            logger.error(f"HydroShare API error: {str(e)}")
        
        return None
    
    # ===============================
    # RISK ASSESSMENT METHODS
    # ===============================
    
    def _assess_flood_risk(self, forecast_data: Dict) -> Dict:
        """Comprehensive flood risk assessment"""
        risk_assessment = {
            'overall_risk': 'LOW',
            'confidence': 0.0,
            'factors': [],
            'recommendations': [],
            'timeline': []
        }
        
        try:
            factors = []
            confidence_factors = []
            
            # Factor 1: Current discharge
            daily_discharge = forecast_data.get('daily', {}).get('river_discharge', [])
            if daily_discharge:
                current_discharge = daily_discharge[0]
                discharge_factor = self._assess_discharge_factor(current_discharge)
                factors.append(discharge_factor)
                confidence_factors.append(discharge_factor.get('confidence', 0.5))
            
            # Factor 2: Forecast trend
            trend_factor = self._assess_forecast_trend(daily_discharge)
            factors.append(trend_factor)
            confidence_factors.append(trend_factor.get('confidence', 0.3))
            
            # Factor 3: Nearby gauges
            nearby_gauges = forecast_data.get('nearby_gauges', [])
            if nearby_gauges:
                gauge_factor = self._assess_gauge_factor(nearby_gauges)
                factors.append(gauge_factor)
                confidence_factors.append(gauge_factor.get('confidence', 0.8))
            
            # Factor 4: Historical comparison
            historical_factor = self._assess_historical_factor(forecast_data)
            factors.append(historical_factor)
            confidence_factors.append(historical_factor.get('confidence', 0.6))
            
            # Calculate overall risk
            risk_levels = [f.get('risk_level', 'LOW') for f in factors]
            if 'EXTREME' in risk_levels:
                overall_risk = 'EXTREME'
            elif 'HIGH' in risk_levels:
                overall_risk = 'HIGH'
            elif 'MODERATE' in risk_levels:
                overall_risk = 'MODERATE'
            else:
                overall_risk = 'LOW'
            
            # Calculate confidence (average of confidence factors)
            confidence = sum(confidence_factors) / len(confidence_factors) if confidence_factors else 0.5
            
            # Generate timeline
            timeline = self._generate_risk_timeline(forecast_data)
            
            # Generate recommendations
            recommendations = self._generate_recommendations(overall_risk, factors)
            
            risk_assessment.update({
                'overall_risk': overall_risk,
                'confidence': round(confidence, 2),
                'factors': factors,
                'recommendations': recommendations,
                'timeline': timeline
            })
            
        except Exception as e:
            logger.error(f"Error in risk assessment: {str(e)}")
            risk_assessment['error'] = str(e)
        
        return risk_assessment
    
    def _assess_discharge_factor(self, discharge: float) -> Dict:
        """Assess risk based on current discharge"""
        factor = {
            'name': 'river_discharge',
            'value': discharge,
            'unit': 'm³/s',
            'risk_level': 'LOW',
            'confidence': 0.9,
            'description': 'Current river discharge'
        }
        
        if discharge >= self.danger_threshold_m3s:
            factor['risk_level'] = 'EXTREME'
            factor['description'] = f'Dangerously high discharge ({discharge:.0f} m³/s)'
        elif discharge >= self.warning_threshold_m3s:
            factor['risk_level'] = 'HIGH'
            factor['description'] = f'Elevated discharge ({discharge:.0f} m³/s)'
        elif discharge >= self.warning_threshold_m3s * 0.7:
            factor['risk_level'] = 'MODERATE'
            factor['description'] = f'Moderate discharge ({discharge:.0f} m³/s)'
        else:
            factor['risk_level'] = 'LOW'
            factor['description'] = f'Normal discharge ({discharge:.0f} m³/s)'
        
        return factor
    
    def _assess_forecast_trend(self, discharge_series: List[float]) -> Dict:
        """Assess risk based on forecast trend"""
        factor = {
            'name': 'forecast_trend',
            'risk_level': 'LOW',
            'confidence': 0.7,
            'description': 'Forecast trend analysis'
        }
        
        if not discharge_series or len(discharge_series) < 3:
            factor['confidence'] = 0.3
            return factor
        
        # Analyze trend over next 24-48 hours
        forecast_horizon = min(2, len(discharge_series))
        forecast_values = discharge_series[:forecast_horizon]
        current = forecast_values[0]
        
        if forecast_horizon > 1:
            future = max(forecast_values[1:])
            increase_pct = ((future - current) / current) * 100 if current > 0 else 0
            
            if increase_pct > 50:
                factor['risk_level'] = 'HIGH'
                factor['description'] = f'Rapid increase forecasted ({increase_pct:.0f}%)'
                factor['value'] = increase_pct
                factor['unit'] = '% increase'
            elif increase_pct > 20:
                factor['risk_level'] = 'MODERATE'
                factor['description'] = f'Moderate increase forecasted ({increase_pct:.0f}%)'
                factor['value'] = increase_pct
                factor['unit'] = '% increase'
            else:
                factor['risk_level'] = 'LOW'
                factor['description'] = 'Stable or decreasing forecast'
        
        return factor
    
    def _assess_gauge_factor(self, gauges: List[Dict]) -> Dict:
        """Assess risk based on nearby river gauges"""
        factor = {
            'name': 'nearby_gauges',
            'risk_level': 'LOW',
            'confidence': 0.8,
            'description': 'Nearby river gauge status',
            'gauges_at_risk': 0,
            'total_gauges': len(gauges)
        }
        
        gauges_at_risk = 0
        for gauge in gauges:
            current = gauge.get('current_level', 0)
            danger = gauge.get('danger_level', float('inf'))
            warning = gauge.get('warning_level', float('inf'))
            
            if current >= danger:
                gauges_at_risk += 1
            elif current >= warning:
                gauges_at_risk += 0.5  # Half weight for warning level
        
        factor['gauges_at_risk'] = gauges_at_risk
        
        if gauges_at_risk >= 2:
            factor['risk_level'] = 'HIGH'
            factor['description'] = f'Multiple gauges at risk ({gauges_at_risk})'
        elif gauges_at_risk >= 1:
            factor['risk_level'] = 'MODERATE'
            factor['description'] = f'Some gauges at risk ({gauges_at_risk})'
        else:
            factor['risk_level'] = 'LOW'
            factor['description'] = 'All gauges normal'
        
        return factor
    
    def _assess_historical_factor(self, forecast_data: Dict) -> Dict:
        """Assess risk based on historical comparison"""
        factor = {
            'name': 'historical_comparison',
            'risk_level': 'LOW',
            'confidence': 0.6,
            'description': 'Historical flood comparison'
        }
        
        # This would typically compare with historical flood events
        # For now, return a placeholder
        return factor
    
    def _generate_risk_timeline(self, forecast_data: Dict) -> List[Dict]:
        """Generate risk timeline for next 24-72 hours"""
        timeline = []
        
        try:
            daily_data = forecast_data.get('daily', {})
            times = daily_data.get('time', [])
            discharges = daily_data.get('river_discharge', [])
            
            for i in range(min(3, len(times))):  # Next 3 days
                if i < len(discharges):
                    risk_level = self._get_risk_for_discharge(discharges[i])
                    
                    timeline.append({
                        'time': times[i],
                        'discharge': discharges[i],
                        'risk_level': risk_level,
                        'hours_from_now': i * 24
                    })
        
        except Exception as e:
            logger.error(f"Error generating timeline: {str(e)}")
        
        return timeline
    
    def _generate_recommendations(self, risk_level: str, factors: List[Dict]) -> List[str]:
        """Generate recommendations based on risk level"""
        recommendations = []
        
        if risk_level == 'EXTREME':
            recommendations = [
                "IMMEDIATE EVACUATION: Move to higher ground immediately",
                "Alert local authorities and emergency services",
                "Do not attempt to cross flooded areas",
                "Secure important documents and medicines",
                "Turn off electricity and gas if safe to do so"
            ]
        elif risk_level == 'HIGH':
            recommendations = [
                "Prepare for possible evacuation",
                "Move livestock and equipment to higher ground",
                "Stock up on essential supplies (food, water, medicine)",
                "Monitor official flood warnings",
                "Prepare emergency kit with important documents"
            ]
        elif risk_level == 'MODERATE':
            recommendations = [
                "Monitor river levels regularly",
                "Review evacuation plans",
                "Secure loose items around property",
                "Check drainage systems are clear",
                "Stay informed through official channels"
            ]
        else:  # LOW
            recommendations = [
                "Continue normal activities",
                "Stay informed about weather forecasts",
                "Review emergency plans periodically",
                "Maintain drainage systems",
                "Report any unusual water level changes"
            ]
        
        return recommendations
    
    # ===============================
    # UTILITY METHODS
    # ===============================
    
    def _calculate_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculate distance between two points in kilometers (Haversine formula)"""
        R = 6371  # Earth's radius in kilometers
        
        lat1_rad = math.radians(lat1)
        lon1_rad = math.radians(lon1)
        lat2_rad = math.radians(lat2)
        lon2_rad = math.radians(lon2)
        
        dlat = lat2_rad - lat1_rad
        dlon = lon2_rad - lon1_rad
        
        a = math.sin(dlat/2)**2 + math.cos(lat1_rad) * math.cos(lat2_rad) * math.sin(dlon/2)**2
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
        
        return R * c
    
    def _calculate_weighted_discharge(self, forecast_data: Dict, gauge_data: List[Dict]) -> float:
        """Calculate weighted average discharge based on nearby gauges"""
        total_weight = 0
        weighted_sum = 0
        
        for gauge in gauge_data:
            distance = gauge.get('distance_km', self.radius_km)
            current_level = gauge.get('current_level')
            
            if current_level is not None:
                # Weight inversely proportional to distance
                weight = 1 / (distance + 1)  # +1 to avoid division by zero
                weighted_sum += current_level * weight
                total_weight += weight
        
        # If we have gauge data, use weighted average
        if total_weight > 0:
            return weighted_sum / total_weight
        
        # Otherwise use forecast data
        daily_discharge = forecast_data.get('daily', {}).get('river_discharge', [])
        return daily_discharge[0] if daily_discharge else 0
    
    def _get_risk_for_discharge(self, discharge: float) -> str:
        """Get risk level for a given discharge value"""
        if discharge >= self.danger_threshold_m3s:
            return 'RED'
        elif discharge >= self.warning_threshold_m3s:
            return 'ORANGE'
        else:
            return 'GREEN'
    
    # ===============================
    # PUBLIC METHODS
    # ===============================
    
    def get_flood_summary(self, latitude: float, longitude: float) -> Dict:
        """
        Get a simplified flood summary for quick display
        
        Args:
            latitude: Location latitude
            longitude: Location longitude
            
        Returns:
            Simplified flood summary dictionary
        """
        forecast = self.get_flood_forecast(latitude, longitude)
        
        if not forecast:
            return {
                'status': 'UNKNOWN',
                'message': 'Unable to retrieve flood data',
                'timestamp': timezone.now().isoformat(),
                'source': 'unknown'
            }
        
        risk_level = self.calculate_risk_level(forecast)
        risk_assessment = forecast.get('risk_assessment', {})
        
        # Get current discharge
        daily_discharge = forecast.get('daily', {}).get('river_discharge', [])
        current_discharge = daily_discharge[0] if daily_discharge else 0
        
        summary = {
            'status': risk_level,
            'current_discharge_m3s': current_discharge,
            'warning_threshold': self.warning_threshold_m3s,
            'danger_threshold': self.danger_threshold_m3s,
            'confidence': risk_assessment.get('confidence', 0.5),
            'message': self._get_status_message(risk_level, current_discharge),
            'recommendations': risk_assessment.get('recommendations', []),
            'next_update': (timezone.now() + timedelta(hours=3)).isoformat(),
            'timestamp': timezone.now().isoformat(),
            'source': forecast.get('source', 'unknown'),
            'location': {
                'latitude': latitude,
                'longitude': longitude
            }
        }
        
        return summary
    
    def _get_status_message(self, risk_level: str, discharge: float) -> str:
        """Get human-readable status message"""
        messages = {
            'RED': f"🚨 DANGER: Flood level critical ({discharge:.0f} m³/s). Evacuation advised.",
            'ORANGE': f"⚠️ WARNING: Flood level elevated ({discharge:.0f} m³/s). Prepare for possible flooding.",
            'GREEN': f"✅ SAFE: Normal river conditions ({discharge:.0f} m³/s).",
            'UNKNOWN': "❓ UNKNOWN: Unable to determine flood status."
        }
        return messages.get(risk_level, messages['UNKNOWN'])
    
    def clear_cache(self):
        """Clear the service cache"""
        self._cache.clear()
        logger.info("Flood service cache cleared")


# ===============================
# HELPER FUNCTIONS
# ===============================

def update_user_flood_alert(user_id: int) -> Dict:
    """
    Update flood alert for a specific user
    This function is kept for backward compatibility
    
    Args:
        user_id: User ID to update
        
    Returns:
        Update result dictionary
    """
    from ..models import User
    
    try:
        user = User.objects.get(id=user_id)
        flood_service = FloodRiskService()
        
        # Get user's location
        if not user.profile.latitude or not user.profile.longitude:
            return {'error': 'User has no location data'}
        
        # Get flood forecast
        forecast = flood_service.get_flood_forecast(
            float(user.profile.latitude),
            float(user.profile.longitude)
        )
        
        if not forecast:
            return {'error': 'Could not retrieve flood data'}
        
        # Calculate risk level
        risk_level = flood_service.calculate_risk_level(forecast)
        
        return {
            'user_id': user_id,
            'risk_level': risk_level,
            'discharge': forecast.get('daily', {}).get('river_discharge', [0])[0],
            'timestamp': timezone.now().isoformat(),
            'success': True
        }
        
    except User.DoesNotExist:
        return {'error': 'User not found'}
    except Exception as e:
        logger.error(f"Error updating flood alert for user {user_id}: {str(e)}")
        return {'error': str(e)}


def batch_process_locations(locations: List[Tuple[float, float]]) -> List[Dict]:
    """
    Batch process multiple locations for flood assessment
    
    Args:
        locations: List of (latitude, longitude) tuples
        
    Returns:
        List of flood assessment results
    """
    flood_service = FloodRiskService()
    results = []
    
    for lat, lon in locations:
        try:
            summary = flood_service.get_flood_summary(lat, lon)
            results.append({
                'location': {'latitude': lat, 'longitude': lon},
                'summary': summary,
                'success': True
            })
        except Exception as e:
            results.append({
                'location': {'latitude': lat, 'longitude': lon},
                'error': str(e),
                'success': False
            })
    
    return results


# ===============================
# CELERY TASK COMPATIBILITY
# ===============================

def trigger_flood_update_for_user(user_id: int) -> Dict:
    """
    Compatible function for Celery tasks
    Updates flood alert and returns result
    """
    return update_user_flood_alert(user_id)