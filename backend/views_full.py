# views.py
from rest_framework import status, viewsets, permissions
from rest_framework.decorators import api_view, action, permission_classes
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated, AllowAny
from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.pagination import PageNumberPagination
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Count, Q, Max
from django.contrib.auth.models import User
from datetime import timedelta
import json
from django.conf import settings

# Import from YOUR NEW serializers.py
from .serializers import (
    UserProfileSerializer,
    FloodAlertSerializer,
    RiverGaugeSerializer,
    NotificationLogSerializer,
    RegisterSerializer,
    ChangePasswordSerializer,
    FloodAlertCreateSerializer,
    AlertStatsSerializer,
    LocationValidationSerializer,
    UserSerializer
)

# Import from YOUR models
from .models import (
    UserProfile,
    FloodAlert,
    RiverGauge,
    FloodNotificationLog
)

# Import from YOUR tasks
from .tasks import refresh_single_user_alert, refresh_all_flood_alerts

# Import from YOUR services
from .services.flood_service import FloodRiskService

# ===============================
# CUSTOM PERMISSIONS
# ===============================

class IsOwnerOrAdmin(permissions.BasePermission):
    """
    Custom permission: Only allow owners or admins to access
    """
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user


class CanUpdateFloodSettings(permissions.BasePermission):
    """
    Custom permission: Users can only update their own flood settings
    """
    def has_permission(self, request, view):
        if request.method in permissions.SAFE_METHODS:
            return True
        return request.user.is_authenticated
    
    def has_object_permission(self, request, view, obj):
        if request.user.is_staff:
            return True
        return obj.user == request.user


# ===============================
# CUSTOM PAGINATION
# ===============================

class FloodAlertPagination(PageNumberPagination):
    """
    Custom pagination for flood alerts
    """
    page_size = 20
    page_size_query_param = 'page_size'
    max_page_size = 100
    
    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'next': self.get_next_link(),
            'previous': self.get_previous_link(),
            'page_size': self.page_size,
            'current_page': self.page.number,
            'total_pages': self.page.paginator.num_pages,
            'results': data
        })


# ===============================
# API VIEWSETS
# ===============================

class FloodAlertViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing flood alerts
    Provides CRUD operations for flood alerts
    URL: /api/flood-alerts/
    """
    serializer_class = FloodAlertSerializer
    permission_classes = [IsAuthenticated, IsOwnerOrAdmin]
    pagination_class = FloodAlertPagination
    
    def get_queryset(self):
        """
        Returns alerts for the authenticated user
        Admins can see all alerts
        """
        user = self.request.user
        
        # Base queryset
        queryset = FloodAlert.objects.all().select_related('user')
        
        # Filter by user if not admin
        if not user.is_staff:
            queryset = queryset.filter(user=user)
        
        # Filter by alert level if provided
        alert_level = self.request.query_params.get('level', None)
        if alert_level:
            queryset = queryset.filter(alert_level=alert_level.upper())
        
        # Filter by date range if provided
        start_date = self.request.query_params.get('start_date', None)
        end_date = self.request.query_params.get('end_date', None)
        
        if start_date:
            queryset = queryset.filter(calculated_at__date__gte=start_date)
        if end_date:
            queryset = queryset.filter(calculated_at__date__lte=end_date)
        
        # Filter by active alerts only
        active_only = self.request.query_params.get('active_only', 'false').lower() == 'true'
        if active_only:
            queryset = queryset.filter(
                Q(valid_until__gte=timezone.now()) | 
                Q(valid_until__isnull=True)
            )
        
        # Order by most recent first
        queryset = queryset.order_by('-calculated_at')
        
        return queryset
    
    def perform_create(self, serializer):
        """
        Automatically set the user to the current user when creating
        """
        serializer.save(user=self.request.user)
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """
        Get the current (latest) flood alert for the user
        URL: /api/flood-alerts/current/
        """
        latest_alert = self.get_queryset().first()
        
        if latest_alert:
            serializer = self.get_serializer(latest_alert)
            return Response(serializer.data)
        else:
            return Response({
                'message': 'No flood alerts found',
                'alert_level': 'GREEN',
                'is_active': False
            }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def acknowledge(self, request, pk=None):
        """
        Mark a flood alert as acknowledged by the user
        URL: /api/flood-alerts/{id}/acknowledge/
        """
        alert = self.get_object()
        
        if alert.acknowledged_by_user:
            return Response({
                'message': 'Alert already acknowledged',
                'acknowledged_at': alert.calculated_at
            }, status=status.HTTP_200_OK)
        
        alert.acknowledged_by_user = True
        alert.save()
        
        return Response({
            'message': 'Alert acknowledged successfully',
            'alert_id': alert.id,
            'acknowledged_at': timezone.now()
        }, status=status.HTTP_200_OK)
    
    @action(detail=True, methods=['post'])
    def report_action(self, request, pk=None):
        """
        Report what action user took in response to alert
        URL: /api/flood-alerts/{id}/report_action/
        Body: {"action_taken": "MOVED_LIVESTOCK"}
        """
        alert = self.get_object()
        action_taken = request.data.get('action_taken', '')
        
        if not action_taken:
            return Response(
                {'error': 'action_taken field is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        valid_actions = ['MOVED_PUMPS', 'MOVED_LIVESTOCK', 'EVACUATED', 'PREPARED', '']
        if action_taken not in valid_actions:
            return Response(
                {'error': f'Invalid action. Must be one of: {", ".join(valid_actions)}'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        alert.action_taken = action_taken
        alert.save()
        
        return Response({
            'message': f'Action "{action_taken}" recorded successfully',
            'alert_id': alert.id,
            'reported_at': timezone.now()
        }, status=status.HTTP_200_OK)
    
    @action(detail=False, methods=['get'])
    def stats(self, request):
        """
        Get flood alert statistics for the user
        URL: /api/flood-alerts/stats/
        """
        user = request.user
        time_period = request.query_params.get('period', '7')  # Default 7 days
        
        try:
            days = int(time_period)
        except ValueError:
            days = 7
        
        start_date = timezone.now() - timedelta(days=days)
        
        # Get user's alerts in the period
        alerts = FloodAlert.objects.filter(
            user=user,
            calculated_at__gte=start_date
        )
        
        # Calculate statistics
        total_alerts = alerts.count()
        red_alerts = alerts.filter(alert_level='RED').count()
        orange_alerts = alerts.filter(alert_level='ORANGE').count()
        green_alerts = alerts.filter(alert_level='GREEN').count()
        
        # Average response time (acknowledgement)
        acknowledged_alerts = alerts.filter(acknowledged_by_user=True)
        if acknowledged_alerts.exists():
            # This is simplified - you'd need to track acknowledgement time separately
            avg_response_minutes = 60  # Placeholder
        else:
            avg_response_minutes = None
        
        # Most common action taken
        if alerts.exists():
            actions = alerts.exclude(action_taken='').values('action_taken').annotate(
                count=Count('action_taken')
            ).order_by('-count')
            most_common_action = actions[0]['action_taken'] if actions else None
        else:
            most_common_action = None
        
        data = {
            'period_days': days,
            'start_date': start_date,
            'end_date': timezone.now(),
            'total_alerts': total_alerts,
            'alert_counts': {
                'RED': red_alerts,
                'ORANGE': orange_alerts,
                'GREEN': green_alerts
            },
            'acknowledgement_rate': (acknowledged_alerts.count() / total_alerts * 100) if total_alerts > 0 else 0,
            'most_common_action': most_common_action,
            'avg_response_minutes': avg_response_minutes
        }
        
        serializer = AlertStatsSerializer(data)
        return Response(serializer.data)


class UserProfileViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing user flood alert preferences
    URL: /api/flood-profile/
    """
    serializer_class = UserProfileSerializer
    permission_classes = [IsAuthenticated, CanUpdateFloodSettings]
    
    def get_queryset(self):
        """
        Users can only see their own profile
        Admins can see all profiles
        """
        user = self.request.user
        if user.is_staff:
            return UserProfile.objects.all().select_related('user')
        return UserProfile.objects.filter(user=user)
    
    def get_object(self):
        """
        Get the user's profile. Creates one if it doesn't exist.
        """
        user = self.request.user
        profile, created = UserProfile.objects.get_or_create(user=user)
        return profile
    
    @action(detail=False, methods=['post'])
    def update_location(self, request):
        """
        Update user's location for flood alerts
        URL: /api/flood-profile/update_location/
        Body: {"latitude": 25.3176, "longitude": 82.9739}
        """
        profile = self.get_object()
        
        latitude = request.data.get('latitude')
        longitude = request.data.get('longitude')
        
        if latitude is None or longitude is None:
            return Response(
                {'error': 'Both latitude and longitude are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lat_float = float(latitude)
            lon_float = float(longitude)
            
            # Validate coordinates (simple range check for India)
            if not (6.0 <= lat_float <= 38.0) or not (68.0 <= lon_float <= 98.0):
                return Response(
                    {'error': 'Coordinates appear to be outside India. Please check values.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            profile.latitude = lat_float
            profile.longitude = lon_float
            profile.save()
            
            # Trigger immediate flood alert update
            refresh_single_user_alert.delay(request.user.id)
            
            return Response({
                'message': 'Location updated successfully',
                'latitude': profile.latitude,
                'longitude': profile.longitude,
                'alert_update_triggered': True
            })
            
        except ValueError:
            return Response(
                {'error': 'Invalid latitude/longitude format. Must be numbers.'},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    @action(detail=False, methods=['post'])
    def toggle_alerts(self, request):
        """
        Enable/disable flood alerts for the user
        URL: /api/flood-profile/toggle_alerts/
        Body: {"enabled": true}
        """
        profile = self.get_object()
        
        enabled = request.data.get('enabled')
        
        if enabled is None:
            return Response(
                {'error': 'enabled field is required (true/false)'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        profile.flood_alert_enabled = bool(enabled)
        profile.save()
        
        message = "Flood alerts enabled" if profile.flood_alert_enabled else "Flood alerts disabled"
        
        return Response({
            'message': message,
            'flood_alert_enabled': profile.flood_alert_enabled
        })


class RiverGaugeViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing river gauges (read-only)
    URL: /api/river-gauges/
    """
    serializer_class = RiverGaugeSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    
    def get_queryset(self):
        """
        Get active river gauges, optionally filtered by proximity
        """
        queryset = RiverGauge.objects.filter(is_active=True)
        
        # Filter by proximity if lat/lon provided
        latitude = self.request.query_params.get('lat')
        longitude = self.request.query_params.get('lon')
        radius_km = self.request.query_params.get('radius', 100)  # Default 100km
        
        if latitude and longitude:
            try:
                from django.db.models import F, ExpressionWrapper, FloatField
                from django.db.models.functions import ACos, Cos, Radians, Sin
                
                lat = float(latitude)
                lon = float(longitude)
                radius = float(radius_km)
                
                # Haversine formula for distance calculation
                # Note: This is simplified; for production, use PostGIS or geodjango
                queryset = queryset.annotate(
                    distance=ExpressionWrapper(
                        6371 * ACos(
                            Cos(Radians(lat)) * Cos(Radians(F('latitude'))) *
                            Cos(Radians(F('longitude')) - Radians(lon)) +
                            Sin(Radians(lat)) * Sin(Radians(F('latitude')))
                        ),
                        output_field=FloatField()
                    )
                ).filter(distance__lte=radius).order_by('distance')
                
            except (ValueError, TypeError):
                # If coordinates invalid, return all gauges
                pass
        
        return queryset
    
    @action(detail=False, methods=['get'])
    def nearest(self, request):
        """
        Find the nearest river gauge to user's location
        URL: /api/river-gauges/nearest/
        Requires lat/lon query parameters
        """
        latitude = request.query_params.get('lat')
        longitude = request.query_params.get('lon')
        
        if not latitude or not longitude:
            return Response(
                {'error': 'lat and lon query parameters are required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            lat = float(latitude)
            lon = float(longitude)
            
            # Simple distance calculation (for demo - use proper geodjango in production)
            gauges = RiverGauge.objects.filter(is_active=True)
            
            if not gauges.exists():
                return Response(
                    {'error': 'No active river gauges found'},
                    status=status.HTTP_404_NOT_FOUND
                )
            
            # Find nearest gauge (simplified)
            nearest_gauge = None
            min_distance = float('inf')
            
            for gauge in gauges:
                # Simple Euclidean distance (approximate for small distances)
                distance = ((gauge.latitude - lat) ** 2 + (gauge.longitude - lon) ** 2) ** 0.5
                if distance < min_distance:
                    min_distance = distance
                    nearest_gauge = gauge
            
            if nearest_gauge:
                serializer = self.get_serializer(nearest_gauge)
                return Response({
                    **serializer.data,
                    'distance_km': min_distance * 111,  # Approximate km per degree
                    'user_location': {'latitude': lat, 'longitude': lon}
                })
            else:
                return Response(
                    {'error': 'Could not find nearest gauge'},
                    status=status.HTTP_404_NOT_FOUND
                )
                
        except ValueError:
            return Response(
                {'error': 'Invalid latitude/longitude format'},
                status=status.HTTP_400_BAD_REQUEST
            )


class NotificationLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing notification logs
    URL: /api/notification-logs/
    """
    serializer_class = NotificationLogSerializer
    permission_classes = [IsAuthenticated]
    pagination_class = PageNumberPagination
    
    def get_queryset(self):
        """
        Users can only see their own notification logs
        Admins can see all
        """
        user = self.request.user
        
        if user.is_staff:
            return FloodNotificationLog.objects.all().select_related('user', 'alert')
        
        return FloodNotificationLog.objects.filter(
            user=user
        ).select_related('alert').order_by('-sent_at')


# ===============================
# FUNCTION-BASED API VIEWS
# ===============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_flood_status(request):
    """
    Get current flood status for authenticated user
    URL: /api/flood-status/
    METHOD: GET
    
    Returns:
        - Current alert level
        - Latest alert details
        - Safety recommendations
    """
    user = request.user
    
    # Get user's profile and location
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        return Response({
            'error': 'User profile not found. Please set your location first.',
            'required_action': 'update_location'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Check if user has location data
    if not profile.latitude or not profile.longitude:
        return Response({
            'error': 'Location not set. Please update your location to get flood alerts.',
            'required_action': 'update_location',
            'profile_id': profile.id
        }, status=status.HTTP_400_BAD_REQUEST)
    
    # Check if flood alerts are enabled
    if not profile.flood_alert_enabled:
        return Response({
            'warning': 'Flood alerts are disabled for your account.',
            'alert_level': 'UNKNOWN',
            'flood_alert_enabled': False,
            'recommendation': 'Enable flood alerts in your profile settings.'
        }, status=status.HTTP_200_OK)
    
    # Get latest alert
    latest_alert = FloodAlert.objects.filter(user=user).order_by('-calculated_at').first()
    
    # If no alert or alert expired, trigger refresh
    needs_refresh = (
        not latest_alert or 
        not latest_alert.is_active() or
        request.query_params.get('force_refresh', 'false').lower() == 'true'
    )
    
    if needs_refresh:
        # Trigger async refresh
        refresh_single_user_alert.delay(user.id)
        
        if latest_alert:
            # Return expired alert with refresh notice
            serializer = FloodAlertSerializer(latest_alert)
            return Response({
                **serializer.data,
                'is_active': False,
                'refreshing': True,
                'message': 'Alert expired. Refreshing data...'
            })
        else:
            # No previous alert
            return Response({
                'alert_level': 'UNKNOWN',
                'is_active': False,
                'refreshing': True,
                'message': 'No flood data available. Fetching latest information...',
                'estimated_wait_seconds': 30
            })
    
    # Return current active alert
    serializer = FloodAlertSerializer(latest_alert)
    return Response({
        **serializer.data,
        'is_active': latest_alert.is_active(),
        'refreshing': False
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def force_refresh_flood_status(request):
    """
    Manually trigger flood status refresh
    URL: /api/flood-status/refresh/
    METHOD: POST
    
    Returns:
        - Refresh status
        - Task ID for tracking
    """
    user = request.user
    
    # Check if user has location data
    try:
        profile = UserProfile.objects.get(user=user)
        if not profile.latitude or not profile.longitude:
            return Response({
                'error': 'Location not set. Please update your location first.',
                'required_action': 'update_location'
            }, status=status.HTTP_400_BAD_REQUEST)
    except UserProfile.DoesNotExist:
        return Response({
            'error': 'User profile not found.',
            'required_action': 'create_profile'
        }, status=status.HTTP_404_NOT_FOUND)
    
    # Trigger refresh
    task = refresh_single_user_alert.delay(user.id)
    
    return Response({
        'message': 'Flood status refresh initiated',
        'task_id': task.id,
        'status': 'queued',
        'user_id': user.id,
        'estimated_completion': '30 seconds',
        'poll_url': f'/api/tasks/{task.id}/status/'  # If you have task status endpoint
    }, status=status.HTTP_202_ACCEPTED)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def simulate_flood_alert(request):
    """
    TEST ENDPOINT: Simulate a flood alert (for development/demo)
    URL: /api/flood-status/simulate/
    METHOD: POST
    Body: {"alert_level": "RED", "discharge": 5500.0}
    
    Note: Only available in DEBUG mode or for staff users
    """
    if not settings.DEBUG and not request.user.is_staff:
        return Response(
            {'error': 'This endpoint is only available in debug mode or for staff users'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    alert_level = request.data.get('alert_level', 'RED').upper()
    discharge = request.data.get('discharge', 5500.0)
    
    if alert_level not in ['GREEN', 'ORANGE', 'RED']:
        return Response(
            {'error': 'alert_level must be GREEN, ORANGE, or RED'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    try:
        discharge_value = float(discharge)
    except ValueError:
        return Response(
            {'error': 'discharge must be a number'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create simulated alert
    profile, created = UserProfile.objects.get_or_create(user=request.user)
    
    alert = FloodAlert.objects.create(
        user=request.user,
        alert_level=alert_level,
        latitude=profile.latitude or 25.3176,
        longitude=profile.longitude or 82.9739,
        river_discharge=discharge_value,
        forecast_discharge=discharge_value,
        warning_threshold=3000.0,
        danger_threshold=5000.0,
        alert_message=f"SIMULATED {alert_level} ALERT: Test flood alert with discharge {discharge_value} m³/s",
        calculated_at=timezone.now(),
        valid_until=timezone.now() + timedelta(hours=1),
        acknowledged_by_user=False
    )
    
    # Send notifications for ORANGE/RED alerts
    if alert_level in ['ORANGE', 'RED']:
        from .tasks import send_flood_notifications
        send_flood_notifications.delay(request.user, alert, None)
    
    serializer = FloodAlertSerializer(alert)
    
    return Response({
        'message': f'Simulated {alert_level} alert created',
        'alert': serializer.data,
        'notifications_sent': alert_level in ['ORANGE', 'RED'],
        'note': 'This is a simulated alert for testing purposes'
    }, status=status.HTTP_201_CREATED)


@api_view(['GET'])
@permission_classes([AllowAny])
def public_flood_map(request):
    """
    Public endpoint for flood map data (read-only, no auth required)
    URL: /api/public/flood-map/
    
    Returns aggregated flood data for mapping (no user-specific info)
    """
    # Only show recent alerts (last 24 hours)
    recent_cutoff = timezone.now() - timedelta(hours=24)
    
    # Aggregate alerts by approximate location (rounded to 2 decimal places)
    # This provides a heatmap-like view without exposing exact user locations
    alerts = FloodAlert.objects.filter(
        calculated_at__gte=recent_cutoff,
        alert_level__in=['RED', 'ORANGE']
    ).extra({
        'lat_bin': "ROUND(latitude, 2)",
        'lon_bin': "ROUND(longitude, 2)"
    }).values('lat_bin', 'lon_bin', 'alert_level').annotate(
        count=Count('id'),
        max_discharge=Max('river_discharge')
    ).order_by('-count')[:100]  # Limit to 100 hotspots
    
    # Get active river gauges
    gauges = RiverGauge.objects.filter(is_active=True).values(
        'id', 'name', 'latitude', 'longitude', 
        'river_name', 'warning_level', 'danger_level'
    )
    
    return Response({
        'data_type': 'flood_heatmap',
        'timestamp': timezone.now(),
        'time_range_hours': 24,
        'hotspots': list(alerts),
        'river_gauges': list(gauges),
        'disclaimer': 'Data is aggregated and anonymized. Not for navigation or emergency response.'
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def get_flood_forecast_raw(request):
    """
    Get raw flood forecast data from API (for debugging/advanced users)
    URL: /api/flood-forecast/raw/
    
    Returns the raw API response from flood service
    """
    user = request.user
    
    try:
        profile = UserProfile.objects.get(user=user)
        if not profile.latitude or not profile.longitude:
            return Response(
                {'error': 'Location not set'},
                status=status.HTTP_400_BAD_REQUEST
            )
    except UserProfile.DoesNotExist:
        return Response(
            {'error': 'User profile not found'},
            status=status.HTTP_404_NOT_FOUND
        )
    
    # Get raw forecast data
    flood_service = FloodRiskService()
    forecast = flood_service.get_flood_forecast(
        float(profile.latitude),
        float(profile.longitude)
    )
    
    if not forecast:
        # Try fallback
        gdacs_data = flood_service.get_gdacs_alerts(
            float(profile.latitude),
            float(profile.longitude)
        )
        forecast = {
            'source': 'gdacs_fallback',
            'alert_level': gdacs_data,
            'note': 'Primary API failed, using GDACS fallback'
        }
    else:
        forecast['source'] = 'openmeteo_primary'
    
    # Add metadata
    forecast['metadata'] = {
        'user_id': user.id,
        'latitude': profile.latitude,
        'longitude': profile.longitude,
        'retrieved_at': timezone.now().isoformat(),
        'thresholds': {
            'warning': flood_service.warning_threshold_m3s,
            'danger': flood_service.danger_threshold_m3s
        }
    }
    
    return Response(forecast)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def send_test_notification(request):
    """
    Send a test notification to verify notification channels work
    URL: /api/notifications/test/
    METHOD: POST
    Body: {"channels": ["email", "sms"]}
    """
    user = request.user
    
    channels = request.data.get('channels', ['email'])
    
    if not isinstance(channels, list):
        return Response(
            {'error': 'channels must be a list'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create a test alert
    test_alert = FloodAlert.objects.create(
        user=user,
        alert_level='ORANGE',
        latitude=request.user.profile.latitude or 25.3176,
        longitude=request.user.profile.longitude or 82.9739,
        river_discharge=3500.0,
        alert_message="TEST NOTIFICATION: This is a test flood alert to verify notification channels.",
        calculated_at=timezone.now(),
        valid_until=timezone.now() + timedelta(minutes=30)
    )
    
    # Update profile to enable requested channels
    profile = user.profile
    
    results = {}
    
    if 'email' in channels:
        profile.receive_email_alerts = True
        from .tasks import send_flood_email
        try:
            send_flood_email.delay(user.email, test_alert)
            results['email'] = {'status': 'queued', 'to': user.email}
        except Exception as e:
            results['email'] = {'status': 'failed', 'error': str(e)}
    
    if 'sms' in channels and hasattr(profile, 'phone_number') and profile.phone_number:
        profile.receive_sms_alerts = True
        from .tasks import send_flood_sms
        try:
            send_flood_sms.delay(profile.phone_number, test_alert)
            results['sms'] = {'status': 'queued', 'to': profile.phone_number}
        except Exception as e:
            results['sms'] = {'status': 'failed', 'error': str(e)}
    
    profile.save()
    
    return Response({
        'message': 'Test notifications queued',
        'alert_id': test_alert.id,
        'results': results,
        'note': 'Test alert will expire in 30 minutes'
    })


# ===============================
# NEW VIEWS TO ADD
# ===============================

@api_view(['POST'])
@permission_classes([AllowAny])
def register_user(request):
    """
    Register a new user with flood alert profile
    URL: /api/register/
    """
    serializer = RegisterSerializer(data=request.data)
    if serializer.is_valid():
        user = serializer.save()
        
        # Get tokens for immediate login
        from rest_framework_simplejwt.tokens import RefreshToken
        refresh = RefreshToken.for_user(user)
        
        return Response({
            'message': 'User registered successfully',
            'user': {
                'id': user.id,
                'username': user.username,
                'email': user.email
            },
            'tokens': {
                'refresh': str(refresh),
                'access': str(refresh.access_token),
            }
        }, status=status.HTTP_201_CREATED)
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def change_password(request):
    """
    Change user password
    URL: /api/change-password/
    """
    serializer = ChangePasswordSerializer(
        data=request.data,
        context={'request': request}
    )
    
    if serializer.is_valid():
        serializer.save()
        return Response({
            'message': 'Password changed successfully'
        })
    
    return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@permission_classes([AllowAny])
def health_check(request):
    """
    Health check endpoint
    URL: /api/health/
    """
    from django.db import connection
    from django.core.cache import cache
    
    checks = {
        'status': 'healthy',
        'timestamp': timezone.now().isoformat(),
        'services': {}
    }
    
    # Database check
    try:
        connection.ensure_connection()
        checks['services']['database'] = 'healthy'
    except Exception as e:
        checks['services']['database'] = f'unhealthy: {str(e)}'
        checks['status'] = 'degraded'
    
    # Cache check
    try:
        cache.set('health_check', 'ok', 10)
        if cache.get('health_check') == 'ok':
            checks['services']['cache'] = 'healthy'
    except Exception as e:
        checks['services']['cache'] = f'unhealthy: {str(e)}'
        checks['status'] = 'degraded'
    
    status_code = 200 if checks['status'] == 'healthy' else 503
    return Response(checks, status=status_code)


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def current_user(request):
    """
    Get current user information
    URL: /api/current-user/
    """
    serializer = UserSerializer(request.user)
    return Response(serializer.data)


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def validate_location(request):
    """
    Validate location coordinates
    URL: /api/validate-location/
    """
    serializer = LocationValidationSerializer(data=request.data)
    if serializer.is_valid():
        return Response({
            'valid': True,
            'message': 'Location coordinates are valid',
            'latitude': serializer.validated_data['latitude'],
            'longitude': serializer.validated_data['longitude']
        })
    
    return Response({
        'valid': False,
        'errors': serializer.errors
    }, status=status.HTTP_400_BAD_REQUEST)


# ===============================
# ADMIN/STAFF ONLY ENDPOINTS
# ===============================

@api_view(['GET'])
@permission_classes([IsAuthenticated])
def admin_flood_stats(request):
    """
    Admin endpoint: Get flood alert statistics across all users
    URL: /api/admin/flood-stats/
    Only accessible to staff users
    """
    if not request.user.is_staff:
        return Response(
            {'error': 'Administrator access required'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    time_period = request.query_params.get('period', '1')  # Default 1 day
    try:
        days = int(time_period)
    except ValueError:
        days = 1
    
    start_date = timezone.now() - timedelta(days=days)
    
    # Overall statistics
    total_alerts = FloodAlert.objects.filter(calculated_at__gte=start_date).count()
    red_alerts = FloodAlert.objects.filter(
        calculated_at__gte=start_date,
        alert_level='RED'
    ).count()
    orange_alerts = FloodAlert.objects.filter(
        calculated_at__gte=start_date,
        alert_level='ORANGE'
    ).count()
    
    # User statistics
    users_with_alerts = User.objects.filter(
        flood_alerts__calculated_at__gte=start_date
    ).distinct().count()
    
    users_with_red_alerts = User.objects.filter(
        flood_alerts__calculated_at__gte=start_date,
        flood_alerts__alert_level='RED'
    ).distinct().count()
    
    # Region statistics (simplified)
    region_alerts = FloodAlert.objects.filter(
        calculated_at__gte=start_date,
        alert_level__in=['RED', 'ORANGE']
    ).extra({
        'region': "CONCAT(ROUND(latitude, 1), ',', ROUND(longitude, 1))"
    }).values('region').annotate(
        alert_count=Count('id'),
        red_count=Count('id', filter=Q(alert_level='RED'))
    ).order_by('-alert_count')[:10]
    
    # Notification statistics
    notifications_sent = FloodNotificationLog.objects.filter(
        sent_at__gte=start_date
    ).count()
    
    notifications_delivered = FloodNotificationLog.objects.filter(
        sent_at__gte=start_date,
        delivery_status='DELIVERED'
    ).count()
    
    delivery_rate = (notifications_delivered / notifications_sent * 100) if notifications_sent > 0 else 0
    
    return Response({
        'period': {
            'days': days,
            'start_date': start_date,
            'end_date': timezone.now()
        },
        'alert_statistics': {
            'total_alerts': total_alerts,
            'red_alerts': red_alerts,
            'orange_alerts': orange_alerts,
            'red_alert_percentage': (red_alerts / total_alerts * 100) if total_alerts > 0 else 0
        },
        'user_statistics': {
            'total_users_with_alerts': users_with_alerts,
            'users_with_red_alerts': users_with_red_alerts,
            'percentage_users_affected': (users_with_alerts / User.objects.count() * 100) if User.objects.count() > 0 else 0
        },
        'regional_hotspots': list(region_alerts),
        'notification_statistics': {
            'notifications_sent': notifications_sent,
            'notifications_delivered': notifications_delivered,
            'delivery_rate_percentage': round(delivery_rate, 2),
            'avg_notifications_per_user': (notifications_sent / users_with_alerts) if users_with_alerts > 0 else 0
        },
        'system_status': {
            'river_gauges_active': RiverGauge.objects.filter(is_active=True).count(),
            'river_gauges_total': RiverGauge.objects.count(),
            'users_with_location': UserProfile.objects.filter(
                latitude__isnull=False,
                longitude__isnull=False
            ).count(),
            'users_flood_enabled': UserProfile.objects.filter(flood_alert_enabled=True).count()
        }
    })


@api_view(['POST'])
@permission_classes([IsAuthenticated])
def admin_trigger_global_refresh(request):
    """
    Admin endpoint: Manually trigger refresh for all users
    URL: /api/admin/refresh-all/
    Only accessible to staff users
    """
    if not request.user.is_staff:
        return Response(
            {'error': 'Administrator access required'},
            status=status.HTTP_403_FORBIDDEN
        )
    
    force = request.data.get('force', False)
    
    task = refresh_all_flood_alerts.delay(force)
    
    return Response({
        'message': 'Global flood alert refresh initiated',
        'task_id': task.id,
        'force_refresh': force,
        'status': 'queued',
        'estimated_users': User.objects.filter(
            profile__flood_alert_enabled=True,
            profile__latitude__isnull=False,
            profile__longitude__isnull=False
        ).count()
    }, status=status.HTTP_202_ACCEPTED)

# ===============================

# FRONTEND VIEWS

# ===============================

@api_view(['GET'])

@permission_classes([AllowAny])

def index(request):

    """

    Serve the frontend SPA

    """

    return render(request, 'index.html')

