# models.py
from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone
from django.db.models.signals import post_save
from django.dispatch import receiver

# ===============================
# CORE USER PROFILE MODEL (Add these fields if not existing)
# ===============================
class UserProfile(models.Model):
    """
    EXTENDS USER MODEL - Stores additional user information
    If you already have this, just add the flood-related fields
    """
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    
    # Location fields (CRITICAL for flood alerts)
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        null=True,
        blank=True,
        help_text="User's farm latitude (e.g., 25.3176 for Varanasi)"
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        null=True,
        blank=True,
        help_text="User's farm longitude (e.g., 82.9739 for Varanasi)"
    )
    
    # Flood-specific preferences
    flood_alert_enabled = models.BooleanField(
        default=True,
        help_text="Whether user wants to receive flood alerts"
    )
    
    # Notification preferences
    receive_sms_alerts = models.BooleanField(
        default=True,
        help_text="Send SMS for Red/Orange alerts"
    )
    receive_email_alerts = models.BooleanField(
        default=True,
        help_text="Send email for flood alerts"
    )
    
    # Farm-specific flood risk factors
    farm_elevation = models.FloatField(
        null=True,
        blank=True,
        help_text="Farm elevation in meters (for custom thresholds)"
    )
    distance_to_river = models.FloatField(
        null=True,
        blank=True,
        help_text="Distance to nearest river in km"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    def __str__(self):
        return f"{self.user.email}'s Profile"
    
    class Meta:
        verbose_name = "User Profile"
        verbose_name_plural = "User Profiles"

# ===============================
# FLOOD ALERT MODEL (NEW - Core of Ganga Alerts)
# ===============================
class FloodAlert(models.Model):
    """
    MAIN FLOOD ALERT MODEL - Tracks current and historical flood alerts
    One user can have multiple alert records over time
    """
    ALERT_LEVEL_CHOICES = [
        ('GREEN', 'Green - Safe'),
        ('ORANGE', 'Orange - Warning'),
        ('RED', 'Red - Danger'),
        ('UNKNOWN', 'Unknown Status'),
    ]
    
    user = models.ForeignKey(
        User, 
        on_delete=models.CASCADE,
        related_name='flood_alerts',
        help_text="User receiving this alert"
    )
    
    # Alert information
    alert_level = models.CharField(
        max_length=10,
        choices=ALERT_LEVEL_CHOICES,
        default='GREEN'
    )
    
    alert_message = models.TextField(
        blank=True,
        help_text="Detailed alert message for user"
    )
    
    # Location context
    latitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        help_text="Latitude where alert was calculated"
    )
    longitude = models.DecimalField(
        max_digits=9, 
        decimal_places=6,
        help_text="Longitude where alert was calculated"
    )
    
    # Source data
    river_discharge = models.FloatField(
        null=True,
        blank=True,
        help_text="River discharge in m³/s at alert time"
    )
    
    forecast_discharge = models.FloatField(
        null=True,
        blank=True,
        help_text="Forecasted maximum discharge (next 48h)"
    )
    
    # Thresholds used (allows customization per user/region)
    warning_threshold = models.FloatField(
        default=3000.0,
        help_text="Discharge threshold for Orange alert (m³/s)"
    )
    danger_threshold = models.FloatField(
        default=5000.0,
        help_text="Discharge threshold for Red alert (m³/s)"
    )
    
    # Additional risk factors
    rainfall_prediction = models.FloatField(
        null=True,
        blank=True,
        help_text="Predicted rainfall in mm (from weather API)"
    )
    
    upstream_alert = models.BooleanField(
        default=False,
        help_text="True if upstream stations show flooding"
    )
    
    # Timestamps
    calculated_at = models.DateTimeField(
        default=timezone.now,
        help_text="When this alert was calculated"
    )
    
    valid_until = models.DateTimeField(
        null=True,
        blank=True,
        help_text="When this alert expires (next check)"
    )
    
    # Response tracking
    acknowledged_by_user = models.BooleanField(
        default=False,
        help_text="User has seen this alert"
    )
    
    action_taken = models.CharField(
        max_length=100,
        blank=True,
        choices=[
            ('', 'No action'),
            ('MOVED_PUMPS', 'Moved pumps to high ground'),
            ('MOVED_LIVESTOCK', 'Moved livestock'),
            ('EVACUATED', 'Started evacuation'),
            ('PREPARED', 'Made preparations'),
        ],
        help_text="What action user reported taking"
    )
    
    def __str__(self):
        return f"{self.user.username} - {self.alert_level} at {self.calculated_at.strftime('%Y-%m-%d %H:%M')}"
    
    class Meta:
        ordering = ['-calculated_at']  # Newest first
        indexes = [
            models.Index(fields=['user', 'calculated_at']),
            models.Index(fields=['alert_level', 'calculated_at']),
        ]
        verbose_name = "Flood Alert"
        verbose_name_plural = "Flood Alerts"
    
    def get_urgency_color(self):
        """Returns CSS color for this alert level"""
        colors = {
            'GREEN': '#10B981',  # Green-500
            'ORANGE': '#F59E0B', # Orange-500
            'RED': '#EF4444',    # Red-500
        }
        return colors.get(self.alert_level, '#6B7280')
    
    def is_active(self):
        """Check if alert is still valid (not expired)"""
        if self.valid_until:
            return timezone.now() <= self.valid_until
        # Default: alert valid for 3 hours
        return timezone.now() <= self.calculated_at + timezone.timedelta(hours=3)
    
    def get_recommended_action(self):
        """Returns recommended action based on alert level"""
        actions = {
            'GREEN': "Continue normal operations. Monitor weather updates.",
            'ORANGE': "Move irrigation pumps and portable equipment to high ground. Secure livestock.",
            'RED': "Immediate evacuation recommended. Move to designated safe zones. Do not attempt to cross flowing water.",
        }
        return actions.get(self.alert_level, "Check local authorities for guidance.")

# ===============================
# RIVER GAUGE MODEL (Optional - for tracking sources)
# ===============================
class RiverGauge(models.Model):
    """
    Tracks river gauge stations for reference
    This helps users understand which stations are being monitored
    """
    name = models.CharField(max_length=200)
    station_code = models.CharField(max_length=50, unique=True)
    
    # Location
    latitude = models.DecimalField(max_digits=9, decimal_places=6)
    longitude = models.DecimalField(max_digits=9, decimal_places=6)
    
    # River information
    river_name = models.CharField(max_length=100)
    nearest_city = models.CharField(max_length=100)
    
    # Alert thresholds (official levels)
    warning_level = models.FloatField(help_text="Official warning level (m)")
    danger_level = models.FloatField(help_text="Official danger level (m)")
    
    # Status
    is_active = models.BooleanField(default=True)
    last_updated = models.DateTimeField(null=True, blank=True)
    
    # Data source
    data_source = models.CharField(
        max_length=100,
        choices=[
            ('OPENMETEO', 'Open-Meteo API'),
            ('GDACS', 'GDACS API'),
            ('CWC', 'Central Water Commission'),
            ('MANUAL', 'Manual Entry'),
        ]
    )
    
    def __str__(self):
        return f"{self.name} ({self.river_name})"
    
    class Meta:
        verbose_name = "River Gauge"
        verbose_name_plural = "River Gauges"

# ===============================
# USER NOTIFICATION LOG (Optional)
# ===============================
class FloodNotificationLog(models.Model):
    """
    Logs all flood notifications sent to users
    Useful for debugging and analytics
    """
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    
    alert = models.ForeignKey(
        FloodAlert,
        on_delete=models.CASCADE,
        related_name='notifications'
    )
    
    # Delivery channels
    sent_via_email = models.BooleanField(default=False)
    sent_via_sms = models.BooleanField(default=False)
    sent_via_push = models.BooleanField(default=False)
    
    # Timestamps
    sent_at = models.DateTimeField(auto_now_add=True)
    delivered_at = models.DateTimeField(null=True, blank=True)
    
    # Status
    delivery_status = models.CharField(
        max_length=50,
        choices=[
            ('PENDING', 'Pending'),
            ('SENT', 'Sent'),
            ('DELIVERED', 'Delivered'),
            ('FAILED', 'Failed'),
            ('READ', 'Read'),
        ],
        default='PENDING'
    )
    
    error_message = models.TextField(blank=True)
    
    def __str__(self):
        return f"Notification for {self.user} - {self.sent_at}"
    
    class Meta:
        ordering = ['-sent_at']

# ===============================
# SIGNALS (Automated Profile Creation)
# ===============================
# These signals are now at the bottom of the file as requested

@receiver(post_save, sender=User)
def create_user_profile(sender, instance, created, **kwargs):
    """
    AUTOMATICALLY CREATES UserProfile when a new User is created
    This ensures every user has a profile for flood alerts
    """
    if created:
        UserProfile.objects.create(user=instance)

@receiver(post_save, sender=User)
def save_user_profile(sender, instance, **kwargs):
    """
    SAVES UserProfile when User is saved
    """
    try:
        instance.profile.save()
    except UserProfile.DoesNotExist:
        # Create if doesn't exist (for existing users)
        UserProfile.objects.create(user=instance)