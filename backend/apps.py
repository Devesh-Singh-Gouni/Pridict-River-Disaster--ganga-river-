# apps.py
from django.apps import AppConfig
from django.db.models.signals import post_migrate
from django.utils.translation import gettext_lazy as _
import logging

logger = logging.getLogger(__name__)

class BackendConfig(AppConfig):
    """
    Configuration for the Flood Alerts backend app
    This class configures the Django application with custom settings
    """
    
    # Django requires these attributes
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'backend'  # Must match the folder name
    verbose_name = 'Flood Alert System'  # Display name in admin
    
    def ready(self):
        """
        This method runs when Django starts.
        Used for:
        1. Importing and connecting signals
        2. Setting up scheduled tasks
        3. Initializing services
        4. Creating default data
        """
        logger.info(f"Initializing {self.verbose_name}...")
        
        try:
            # 1. Import signals (for automatic profile creation)
            # import backend.signals
            
            # 2. Setup periodic tasks if Celery is configured
            self.setup_celery_tasks()
            
            # 3. Initialize default river gauges after migrations
            post_migrate.connect(self.create_default_gauges, sender=self)
            
            # 4. Check service dependencies
            self.check_dependencies()
            
            logger.info(f"{self.verbose_name} initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize {self.verbose_name}: {str(e)}")
    
    def setup_celery_tasks(self):
        """
        Setup Celery periodic tasks for flood alerts
        """
        try:
            # Only setup if Celery is installed
            from django.conf import settings
            
            if hasattr(settings, 'CELERY_BROKER_URL'):
                from celery.schedules import crontab
                from celery import Celery
                
                # Import tasks to ensure they're registered
                import backend.tasks
                
                logger.info("Celery tasks registered")
                
                # Setup beat schedule in settings.py instead of here
                # This is just for logging confirmation
                
        except ImportError:
            logger.warning("Celery not installed, background tasks disabled")
        except Exception as e:
            logger.warning(f"Could not setup Celery: {str(e)}")
    
    def create_default_gauges(self, sender, **kwargs):
        """
        Create default river gauges after migrations
        Called automatically after migrate command
        """
        try:
            from .models import RiverGauge
            from django.db import transaction
            
            # Only create if no gauges exist
            if RiverGauge.objects.exists():
                return
            
            # Major river gauges in India (example data)
            default_gauges = [
                {
                    'name': 'Haridwar Gauge',
                    'station_code': 'HAR-001',
                    'latitude': 29.9457,
                    'longitude': 78.1642,
                    'river_name': 'Ganga',
                    'nearest_city': 'Haridwar',
                    'warning_level': 294.0,
                    'danger_level': 295.0,
                    'data_source': 'OPENMETEO'
                },
                {
                    'name': 'Farakka Barrage',
                    'station_code': 'FAR-001',
                    'latitude': 24.7994,
                    'longitude': 87.9200,
                    'river_name': 'Ganga',
                    'nearest_city': 'Farakka',
                    'warning_level': 20.5,
                    'danger_level': 21.0,
                    'data_source': 'OPENMETEO'
                },
                {
                    'name': 'Patna Gauge',
                    'station_code': 'PAT-001',
                    'latitude': 25.6154,
                    'longitude': 85.1015,
                    'river_name': 'Ganga',
                    'nearest_city': 'Patna',
                    'warning_level': 48.5,
                    'danger_level': 49.0,
                    'data_source': 'OPENMETEO'
                },
                {
                    'name': 'Varanasi Gauge',
                    'station_code': 'VAR-001',
                    'latitude': 25.3176,
                    'longitude': 82.9739,
                    'river_name': 'Ganga',
                    'nearest_city': 'Varanasi',
                    'warning_level': 70.0,
                    'danger_level': 71.0,
                    'data_source': 'OPENMETEO'
                },
                {
                    'name': 'Allahabad Gauge',
                    'station_code': 'ALD-001',
                    'latitude': 25.4358,
                    'longitude': 81.8463,
                    'river_name': 'Ganga',
                    'nearest_city': 'Prayagraj',
                    'warning_level': 84.5,
                    'danger_level': 85.0,
                    'data_source': 'OPENMETEO'
                }
            ]
            
            with transaction.atomic():
                for gauge_data in default_gauges:
                    RiverGauge.objects.get_or_create(
                        station_code=gauge_data['station_code'],
                        defaults=gauge_data
                    )
            
            logger.info(f"Created {len(default_gauges)} default river gauges")
            
        except Exception as e:
            logger.error(f"Failed to create default gauges: {str(e)}")
    
    def check_dependencies(self):
        """
        Check if required services are available
        """
        try:
            # Check flood API service
            from .services.flood_service import FloodRiskService
            
            service = FloodRiskService()
            
            # Test with a known location
            test_data = service.get_flood_forecast(25.3176, 82.9739)  # Varanasi
            
            if test_data:
                logger.info("Flood API service is working")
            else:
                logger.warning("Flood API returned no data (might be offline)")
            
            # Check GDACS fallback
            gdacs_data = service.get_gdacs_alerts(25.3176, 82.9739)
            if gdacs_data:
                logger.info("GDACS fallback service is working")
            else:
                logger.warning("GDACS fallback unavailable")
            
        except ImportError as e:
            logger.error(f"Missing service module: {str(e)}")
        except Exception as e:
            logger.error(f"Service check failed: {str(e)}")
    
    def get_system_info(self):
        """
        Return system information for status endpoints
        """
        from .models import UserProfile, FloodAlert, RiverGauge
        from django.contrib.auth.models import User
        
        return {
            'app_name': self.verbose_name,
            'app_version': '1.0.0',
            'models': {
                'UserProfile': UserProfile.objects.count(),
                'FloodAlert': FloodAlert.objects.count(),
                'RiverGauge': RiverGauge.objects.count(),
                'TotalUsers': User.objects.count(),
            },
            'features': {
                'flood_alerts': True,
                'river_monitoring': True,
                'notifications': True,
                'api': True,
            }
        }