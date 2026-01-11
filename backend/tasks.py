# tasks.py
import logging
from celery import shared_task
from celery.exceptions import MaxRetriesExceededError
from django.utils import timezone
from django.contrib.auth.models import User
from django.conf import settings
from datetime import timedelta
import requests

# CORRECTED IMPORTS - Use relative imports for your models
# Based on your structure, you're in the services directory
from ..models import UserProfile, FloodAlert, FloodNotificationLog, RiverGauge

# CORRECTED SERVICE IMPORT - Use relative import for services in the same directory
from .flood_service import FloodRiskService

logger = logging.getLogger(__name__)

# ===============================
# CORE FLOOD ALERT TASKS
# ===============================

@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=300,  # 5 minutes between retries
    time_limit=600,  # 10 minute timeout
    name='flood.tasks.refresh_all_flood_alerts'
)
def refresh_all_flood_alerts(self, force_refresh=False):
    """
    MASTER TASK: Updates flood alerts for ALL users with valid locations
    Runs periodically (every 3 hours) via Celery Beat
    Sends notifications if alert level changes
    
    Parameters:
        force_refresh (bool): If True, updates even if recent check exists
    
    Returns:
        dict: Statistics about the update operation
    """
    logger.info("🚨 Starting refresh_all_flood_alerts task")
    
    stats = {
        'total_users': 0,
        'users_processed': 0,
        'alerts_created': 0,
        'alerts_updated': 0,
        'notifications_sent': 0,
        'errors': 0,
        'start_time': timezone.now().isoformat()
    }
    
    try:
        # Get all users with flood alerts enabled and location data
        users = User.objects.filter(
            profile__flood_alert_enabled=True,
            profile__latitude__isnull=False,
            profile__longitude__isnull=False
        ).select_related('profile')
        
        stats['total_users'] = users.count()
        
        for user in users:
            try:
                # Skip if recently updated (unless forced)
                if not force_refresh:
                    latest_alert = FloodAlert.objects.filter(
                        user=user
                    ).order_by('-calculated_at').first()
                    
                    if latest_alert and latest_alert.is_active():
                        # Alert still valid, skip this user
                        continue
                
                # Process this user's flood alert
                user_stats = refresh_single_user_alert_sync(user)
                
                # Update statistics
                stats['users_processed'] += 1
                stats['alerts_created'] += user_stats.get('created', 0)
                stats['alerts_updated'] += user_stats.get('updated', 0)
                stats['notifications_sent'] += user_stats.get('notifications_sent', 0)
                
            except Exception as e:
                stats['errors'] += 1
                logger.error(f"❌ Error processing user {user.id}: {str(e)}", exc_info=True)
                continue
        
        stats['end_time'] = timezone.now().isoformat()
        stats['duration_seconds'] = (timezone.now() - stats['start_time']).total_seconds()
        
        logger.info(f"✅ refresh_all_flood_alerts completed: {stats}")
        return stats
        
    except Exception as e:
        logger.error(f"❌ Critical error in refresh_all_flood_alerts: {str(e)}", exc_info=True)
        
        # Retry the entire task if it fails
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            logger.critical("❌ Max retries exceeded for refresh_all_flood_alerts")
        
        stats['error'] = str(e)
        return stats


@shared_task(
    bind=True,
    max_retries=2,
    default_retry_delay=60,  # 1 minute between retries
    name='flood.tasks.refresh_single_user_alert'
)
def refresh_single_user_alert(self, user_id):
    """
    Updates flood alert for a SINGLE user
    Called when user logs in or manually refreshes
    
    Parameters:
        user_id (int): ID of the user to update
    
    Returns:
        dict: Update results for this user
    """
    logger.info(f"🔄 Starting refresh_single_user_alert for user {user_id}")
    
    try:
        user = User.objects.get(id=user_id)
        return refresh_single_user_alert_sync(user)
        
    except User.DoesNotExist:
        logger.error(f"❌ User {user_id} not found")
        return {'error': 'User not found', 'user_id': user_id}
        
    except Exception as e:
        logger.error(f"❌ Error in refresh_single_user_alert for user {user_id}: {str(e)}")
        
        # Retry the task
        try:
            self.retry(exc=e)
        except MaxRetriesExceededError:
            logger.error(f"❌ Max retries exceeded for user {user_id}")
        
        return {'error': str(e), 'user_id': user_id}


def refresh_single_user_alert_sync(user):
    """
    SYNCHRONOUS VERSION: Updates flood alert for a user
    Called by both tasks and can be called directly if needed
    """
    user_profile = user.profile
    
    # Validate user has location data
    if not user_profile.latitude or not user_profile.longitude:
        logger.warning(f"⚠️ User {user.id} has no location data")
        return {'error': 'No location data', 'user_id': user.id}
    
    # Get current flood status
    flood_service = FloodRiskService()
    
    # Get flood forecast
    forecast = flood_service.get_flood_forecast(
        float(user_profile.latitude),
        float(user_profile.longitude)
    )
    
    # Fallback to GDACS if primary fails
    if not forecast:
        logger.warning(f"⚠️ Primary API failed for user {user.id}, trying GDACS fallback")
        alert_level = flood_service.get_gdacs_alerts(
            float(user_profile.latitude),
            float(user_profile.longitude)
        ) or "GREEN"
        river_discharge = None
        forecast_discharge = None
    else:
        # Calculate alert level
        alert_level = flood_service.calculate_risk_level(forecast)
        
        # Extract discharge data
        daily_discharge = forecast.get("daily", {}).get("river_discharge", [])
        river_discharge = daily_discharge[0] if daily_discharge else None
        forecast_discharge = max(daily_discharge[:2]) if len(daily_discharge) >= 2 else river_discharge
    
    # Get latest alert to check if level changed
    latest_alert = FloodAlert.objects.filter(user=user).order_by('-calculated_at').first()
    
    alert_changed = False
    if latest_alert:
        alert_changed = (latest_alert.alert_level != alert_level)
    
    # Create or update flood alert
    alert, created = FloodAlert.objects.update_or_create(
        user=user,
        defaults={
            'alert_level': alert_level,
            'latitude': user_profile.latitude,
            'longitude': user_profile.longitude,
            'river_discharge': river_discharge,
            'forecast_discharge': forecast_discharge,
            'warning_threshold': flood_service.warning_threshold_m3s,
            'danger_threshold': flood_service.danger_threshold_m3s,
            'calculated_at': timezone.now(),
            'valid_until': timezone.now() + timedelta(hours=3),
            'alert_message': generate_alert_message(alert_level, forecast_discharge),
            'acknowledged_by_user': False if alert_changed else latest_alert.acknowledged_by_user,
        }
    )
    
    result = {
        'user_id': user.id,
        'alert_id': alert.id,
        'alert_level': alert_level,
        'created': 1 if created else 0,
        'updated': 0 if created else 1,
        'alert_changed': alert_changed,
        'notifications_sent': 0
    }
    
    # Send notifications if alert level changed to Orange/Red
    if alert_changed and alert_level in ['ORANGE', 'RED']:
        notification_count = send_flood_notifications(user, alert, latest_alert)
        result['notifications_sent'] = notification_count
    
    # Log the update
    logger.info(f"📊 User {user.id}: {alert_level} alert {'created' if created else 'updated'}")
    
    return result


# ===============================
# NOTIFICATION TASKS
# ===============================

@shared_task(
    name='flood.tasks.send_flood_notifications',
    queue='notifications'
)
def send_flood_notifications(user, alert, previous_alert=None):
    """
    Sends flood alert notifications through all enabled channels
    Runs in separate 'notifications' queue to avoid blocking main tasks
    
    Parameters:
        user: User object
        alert: Current FloodAlert object
        previous_alert: Previous FloodAlert object (for comparison)
    
    Returns:
        int: Number of notifications successfully sent
    """
    notification_count = 0
    
    # Create notification log entry
    notification_log = FloodNotificationLog.objects.create(
        user=user,
        alert=alert,
        sent_at=timezone.now(),
        delivery_status='PENDING'
    )
    
    user_profile = user.profile
    
    # 1. EMAIL NOTIFICATION
    if user_profile.receive_email_alerts and user.email:
        try:
            send_flood_email.delay(user.email, alert, previous_alert)
            notification_log.sent_via_email = True
            notification_count += 1
        except Exception as e:
            logger.error(f"❌ Failed to queue email for user {user.id}: {str(e)}")
    
    # 2. SMS NOTIFICATION (only for Orange/Red alerts)
    if alert.alert_level in ['ORANGE', 'RED'] and user_profile.receive_sms_alerts:
        try:
            # Get user's phone number (assuming it's stored in profile)
            phone_number = getattr(user_profile, 'phone_number', None)
            if phone_number:
                send_flood_sms.delay(phone_number, alert)
                notification_log.sent_via_sms = True
                notification_count += 1
        except Exception as e:
            logger.error(f"❌ Failed to queue SMS for user {user.id}: {str(e)}")
    
    # 3. PUSH NOTIFICATION (if you have mobile app)
    if hasattr(settings, 'FCM_API_KEY') and alert.alert_level in ['ORANGE', 'RED']:
        try:
            send_flood_push.delay(user.id, alert)
            notification_log.sent_via_push = True
            notification_count += 1
        except Exception as e:
            logger.error(f"❌ Failed to queue push notification for user {user.id}: {str(e)}")
    
    # Update notification log
    notification_log.delivery_status = 'SENT' if notification_count > 0 else 'FAILED'
    notification_log.save()
    
    logger.info(f"📨 Sent {notification_count} notifications for user {user.id}")
    return notification_count


@shared_task(
    name='flood.tasks.send_flood_email',
    queue='email'
)
def send_flood_email(user_email, alert, previous_alert=None):
    """
    Sends flood alert email
    Runs in separate 'email' queue
    """
    from django.core.mail import send_mail
    from django.template.loader import render_to_string
    
    subject = f"🚨 Ganga Alert: {alert.alert_level} Flood Alert"
    
    # Prepare context for email template
    context = {
        'alert': alert,
        'previous_alert': previous_alert,
        'user': alert.user,
        'recommended_action': alert.get_recommended_action(),
        'current_time': timezone.now(),
    }
    
    # Render email templates
    html_message = render_to_string('emails/flood_alert.html', context)
    plain_message = render_to_string('emails/flood_alert.txt', context)
    
    try:
        send_mail(
            subject=subject,
            message=plain_message,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user_email],
            html_message=html_message,
            fail_silently=False,
        )
        logger.info(f"📧 Email sent to {user_email} for alert {alert.id}")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to send email to {user_email}: {str(e)}")
        raise e


@shared_task(
    name='flood.tasks.send_flood_sms',
    queue='sms',
    max_retries=2
)
def send_flood_sms(phone_number, alert):
    """
    Sends flood alert SMS via Twilio or similar service
    Requires SMS service configuration
    """
    # Example using Twilio (you need to install twilio and configure)
    try:
        # Uncomment and configure if you have Twilio
        # from twilio.rest import Client
        
        # client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        
        message_body = generate_sms_message(alert)
        
        # Example Twilio call (commented out)
        # message = client.messages.create(
        #     body=message_body,
        #     from_=settings.TWILIO_PHONE_NUMBER,
        #     to=phone_number
        # )
        
        logger.info(f"📱 SMS queued for {phone_number}: {message_body[:50]}...")
        return True
        
    except ImportError:
        logger.warning("Twilio not installed, SMS disabled")
        return False
    except Exception as e:
        logger.error(f"❌ SMS failed for {phone_number}: {str(e)}")
        raise e


@shared_task(
    name='flood.tasks.send_flood_push',
    queue='push'
)
def send_flood_push(user_id, alert):
    """
    Sends push notification to mobile app via Firebase Cloud Messaging
    Requires FCM setup
    """
    try:
        # This is a placeholder - implement based on your mobile app setup
        logger.info(f"📱 Push notification would be sent to user {user_id}")
        return True
    except Exception as e:
        logger.error(f"❌ Push notification failed for user {user_id}: {str(e)}")
        raise e


# ===============================
# MAINTENANCE & CLEANUP TASKS
# ===============================

@shared_task(
    name='flood.tasks.cleanup_old_alerts',
    queue='maintenance'
)
def cleanup_old_alerts(days_to_keep=30):
    """
    Cleans up old flood alerts to prevent database bloat
    Runs weekly via Celery Beat
    
    Parameters:
        days_to_keep (int): How many days of history to keep
    
    Returns:
        dict: Cleanup statistics
    """
    cutoff_date = timezone.now() - timedelta(days=days_to_keep)
    
    # Delete old alerts (keep only recent ones)
    deleted_count, _ = FloodAlert.objects.filter(
        calculated_at__lt=cutoff_date
    ).delete()
    
    # Also clean up notification logs
    notifications_deleted, _ = FloodNotificationLog.objects.filter(
        sent_at__lt=cutoff_date
    ).delete()
    
    stats = {
        'alerts_deleted': deleted_count,
        'notifications_deleted': notifications_deleted,
        'cutoff_date': cutoff_date.isoformat(),
        'run_at': timezone.now().isoformat()
    }
    
    logger.info(f"🧹 Cleanup completed: {stats}")
    return stats


@shared_task(
    name='flood.tasks.validate_river_gauges',
    queue='maintenance'
)
def validate_river_gauges():
    """
    Checks if river gauge data sources are still active
    Updates gauge status and fetches latest thresholds
    Runs daily
    """
    gauges = RiverGauge.objects.filter(is_active=True)
    
    updated_count = 0
    for gauge in gauges:
        try:
            # Test API connection for this gauge
            if test_gauge_connection(gauge):
                gauge.last_updated = timezone.now()
                gauge.save()
                updated_count += 1
            else:
                # Mark as inactive if unresponsive
                gauge.is_active = False
                gauge.save()
                logger.warning(f"⚠️ Marked gauge {gauge.name} as inactive")
                
        except Exception as e:
            logger.error(f"❌ Error validating gauge {gauge.id}: {str(e)}")
    
    return {
        'gauges_checked': gauges.count(),
        'gauges_updated': updated_count,
        'run_at': timezone.now().isoformat()
    }


@shared_task(
    name='flood.tasks.send_daily_alert_summary',
    queue='reports'
)
def send_daily_alert_summary():
    """
    Sends daily summary of flood alerts to administrators
    Runs every day at 8 AM
    """
    yesterday = timezone.now() - timedelta(days=1)
    
    # Get alert statistics
    alerts_today = FloodAlert.objects.filter(
        calculated_at__gte=yesterday
    )
    
    red_alerts = alerts_today.filter(alert_level='RED').count()
    orange_alerts = alerts_today.filter(alert_level='ORANGE').count()
    
    # Get users affected
    affected_users = User.objects.filter(
        flood_alerts__calculated_at__gte=yesterday,
        flood_alerts__alert_level__in=['RED', 'ORANGE']
    ).distinct().count()
    
    # Prepare summary
    summary = {
        'date': timezone.now().date().isoformat(),
        'total_alerts': alerts_today.count(),
        'red_alerts': red_alerts,
        'orange_alerts': orange_alerts,
        'affected_users': affected_users,
        'most_affected_region': find_most_affected_region(yesterday),
    }
    
    # Send to admin email (placeholder)
    logger.info(f"📊 Daily alert summary: {summary}")
    
    return summary


# ===============================
# HELPER FUNCTIONS
# ===============================

def generate_alert_message(alert_level, discharge_value=None):
    """Generate user-friendly alert message"""
    messages = {
        'GREEN': "No flood risk detected. River conditions are normal.",
        'ORANGE': f"FLOOD WARNING: River levels are rising. Current discharge: {discharge_value:.0f} m³/s. Prepare to move equipment and livestock to higher ground.",
        'RED': f"FLOOD DANGER: River levels exceeding danger threshold at {discharge_value:.0f} m³/s. EVACUATION ADVISED. Move to safe ground immediately.",
    }
    return messages.get(alert_level, "Monitoring river conditions...")


def generate_sms_message(alert):
    """Generate concise SMS message"""
    if alert.alert_level == 'RED':
        return f"RED ALERT: Flood danger! Evacuate now. Discharge: {alert.river_discharge:.0f} m³/s. Stay safe."
    elif alert.alert_level == 'ORANGE':
        return f"ORANGE ALERT: Flood warning. Move pumps/livestock. Discharge: {alert.river_discharge:.0f} m³/s."
    else:
        return f"Ganga Alert: {alert.alert_level}. River discharge: {alert.river_discharge:.0f} m³/s."


def test_gauge_connection(gauge):
    """Test if a river gauge API is responding"""
    try:
        # Simple test - adjust based on your data source
        response = requests.get(
            f"https://flood-api.open-meteo.com/v1/flood",
            params={
                'latitude': gauge.latitude,
                'longitude': gauge.longitude,
                'daily': 'river_discharge',
                'forecast_days': 1
            },
            timeout=5
        )
        return response.status_code == 200
    except:
        return False


def find_most_affected_region(since_date):
    """Find region with most alerts (simplified)"""
    from django.db.models import Count
    
    # Group alerts by approximate region (rounded coordinates)
    regions = FloodAlert.objects.filter(
        calculated_at__gte=since_date,
        alert_level__in=['RED', 'ORANGE']
    ).extra({
        'region': "CONCAT(FLOOR(latitude), ',', FLOOR(longitude))"
    }).values('region').annotate(
        count=Count('id')
    ).order_by('-count')[:1]
    
    return regions[0]['region'] if regions else "Unknown"