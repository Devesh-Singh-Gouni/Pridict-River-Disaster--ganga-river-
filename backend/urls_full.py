# urls.py (for your flood alerts app)
from django.urls import path, include
from django.contrib import admin
from django.conf import settings
from django.conf.urls.static import static
from rest_framework import routers
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView
from drf_yasg.views import get_schema_view
from drf_yasg import openapi
from rest_framework.permissions import AllowAny
import logging

# Import your views
from . import views

logger = logging.getLogger(__name__)

# ===============================
# API SCHEMA CONFIGURATION (Swagger/OpenAPI)
# ===============================
schema_view = get_schema_view(
    openapi.Info(
        title="Ganga Alerts - Flood Monitoring API",
        default_version='v1',
        description="""
        # 🚨 Ganga Alerts API Documentation
        
        ## Overview
        Real-time flood monitoring and alert system for river Ganga basin.
        
        ## Key Features:
        - Real-time flood risk assessment
        - User-specific alert notifications
        - River gauge monitoring
        - SMS/Email notifications
        
        ## Authentication
        Most endpoints require JWT authentication.
        
        ## Quick Start:
        1. Register: `POST /api/auth/register/`
        2. Login: `POST /api/auth/token/`
        3. Set location: `POST /api/profile/update_location/`
        4. Get alerts: `GET /api/alerts/`
        
        ## Alert Levels:
        - 🟢 **GREEN**: Safe conditions (discharge < warning_threshold)
        - 🟠 **ORANGE**: Warning (warning_threshold ≤ discharge < danger_threshold)
        - 🔴 **RED**: Danger (discharge ≥ danger_threshold)
        """,
        terms_of_service="https://yourdomain.com/terms/",
        contact=openapi.Contact(email="support@yourdomain.com"),
        license=openapi.License(name="Proprietary"),
    ),
    public=True,
    permission_classes=[AllowAny],
)

# ===============================
# ROUTER CONFIGURATION (for ViewSets)
# ===============================
router = routers.DefaultRouter()

# Flood Alerts endpoints
router.register(r'alerts', views.FloodAlertViewSet, basename='floodalert')
router.register(r'profile', views.UserProfileViewSet, basename='userprofile')
router.register(r'river-gauges', views.RiverGaugeViewSet, basename='rivergauge')
router.register(r'notification-logs', views.NotificationLogViewSet, basename='notificationlog')

# ===============================
# URL PATTERNS
# ===============================
urlpatterns = [
    # ==================== ADMIN ====================
    path('admin/', admin.site.urls),
    
    # ==================== AUTHENTICATION ====================
    path('auth/token/', TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('auth/token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('auth/register/', views.register_user, name='register'),
    
    # ==================== API DOCUMENTATION ====================
    path('docs/', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    path('redoc/', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    path('swagger.json', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    path('swagger.yaml', schema_view.without_ui(cache_timeout=0), name='schema-yaml'),
    
    # ==================== FLOOD ALERTS API ====================
    # Router-based endpoints (ViewSets)
    path('', include(router.urls)),
    
    # User profile management
    path('profile/update_location/', views.update_user_location, name='update-location'),
    path('profile/notification_preferences/', views.update_notification_preferences, 
         name='notification-preferences'),
    
    # Flood status and monitoring
    path('status/', views.get_flood_status, name='flood-status'),
    path('status/refresh/', views.force_refresh_flood_status, name='refresh-flood-status'),
    path('status/history/', views.get_flood_history, name='flood-history'),
    
    # Flood forecast data
    path('forecast/raw/', views.get_flood_forecast_raw, name='flood-forecast-raw'),
    path('forecast/summary/', views.get_forecast_summary, name='forecast-summary'),
    
    # Alerts management
    path('alerts/acknowledge/<int:alert_id>/', views.acknowledge_alert, name='acknowledge-alert'),
    path('alerts/dismiss/<int:alert_id>/', views.dismiss_alert, name='dismiss-alert'),
    path('alerts/active/', views.get_active_alerts, name='active-alerts'),
    
    # Notifications
    path('notifications/test/', views.send_test_notification, name='test-notification'),
    path('notifications/preferences/', views.get_notification_preferences, 
         name='get-notification-preferences'),
    
    # Simulation endpoints (for testing)
    path('simulate/flood/', views.simulate_flood_alert, name='simulate-flood-alert'),
    path('simulate/rainfall/', views.simulate_rainfall_event, name='simulate-rainfall'),
    
    # ==================== PUBLIC ENDPOINTS ====================
    path('public/map/', views.public_flood_map, name='public-flood-map'),
    path('public/gauges/', views.public_river_gauges, name='public-river-gauges'),
    path('public/alerts/', views.public_active_alerts, name='public-active-alerts'),
    path('public/statistics/', views.public_statistics, name='public-statistics'),
    
    # ==================== HEALTH & MONITORING ====================
    path('health/', views.health_check, name='health-check'),
    path('status/system/', views.system_status, name='system-status'),
    path('metrics/', views.system_metrics, name='system-metrics'),
    
    # ==================== ADMIN API ENDPOINTS ====================
    path('admin/stats/', views.admin_flood_stats, name='admin-flood-stats'),
    path('admin/users/report/', views.admin_user_report, name='admin-user-report'),
    path('admin/alerts/report/', views.admin_alert_report, name='admin-alert-report'),
    path('admin/refresh-all/', views.admin_trigger_global_refresh, name='admin-refresh-all'),
    path('admin/manual-alert/', views.admin_create_manual_alert, name='admin-manual-alert'),
    
    # ==================== WEBHOOKS & INTEGRATIONS ====================
    path('webhooks/flood-data/', views.flood_data_webhook, name='flood-data-webhook'),
    path('webhooks/sms/reply/', views.sms_reply_webhook, name='sms-reply-webhook'),
    path('webhooks/weather/', views.weather_data_webhook, name='weather-data-webhook'),
    
    # ==================== EXPORT ENDPOINTS ====================
    path('export/alerts/csv/', views.export_alerts_csv, name='export-alerts-csv'),
    path('export/alerts/json/', views.export_alerts_json, name='export-alerts-json'),
    path('export/notifications/csv/', views.export_notifications_csv, name='export-notifications-csv'),
    
    # ==================== UTILITY ENDPOINTS ====================
    path('utility/geocode/', views.geocode_address, name='geocode-address'),
    path('utility/distance/', views.calculate_distance, name='calculate-distance'),
    path('utility/timezone/', views.get_timezone_info, name='get-timezone'),
    
    # ==================== FRONTEND CATCH-ALL ====================
    # Note: For SPA, these should be handled by your frontend router
    path('', views.index, name='index'),
    # path('dashboard/', views.index, name='dashboard'),
    # path('alerts/', views.index, name='alerts-view'),
    # path('settings/', views.index, name='settings-view'),
]

# ... existing code ...

# ===============================
# CUSTOM ERROR HANDLERS
# ===============================
# handler400 = 'backend.views.bad_request_view'
# handler403 = 'backend.views.permission_denied_view'
# handler404 = 'backend.views.page_not_found_view'
# handler500 = 'backend.views.server_error_view'