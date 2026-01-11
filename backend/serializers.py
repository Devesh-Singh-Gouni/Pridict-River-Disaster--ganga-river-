# serializers.py
from rest_framework import serializers
from rest_framework.validators import UniqueValidator
from django.contrib.auth.models import User
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
from datetime import timedelta

# Import your models
from .models import (
    UserProfile, 
    FloodAlert, 
    RiverGauge, 
    FloodNotificationLog
)

# ===============================
# USER SERIALIZERS
# ===============================

class UserSerializer(serializers.ModelSerializer):
    """
    Serializer for User model (for reading)
    """
    profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'profile']
        read_only_fields = ['id', 'profile']
    
    def get_profile(self, obj):
        """Get user's flood profile"""
        try:
            profile = obj.profile
            return {
                'latitude': profile.latitude,
                'longitude': profile.longitude,
                'flood_alert_enabled': profile.flood_alert_enabled,
                'receive_email_alerts': profile.receive_email_alerts,
                'receive_sms_alerts': profile.receive_sms_alerts,
            }
        except UserProfile.DoesNotExist:
            return None


class RegisterSerializer(serializers.ModelSerializer):
    """
    Serializer for user registration
    """
    email = serializers.EmailField(
        required=True,
        validators=[UniqueValidator(queryset=User.objects.all())]
    )
    password = serializers.CharField(
        write_only=True, 
        required=True, 
        validators=[validate_password]
    )
    password2 = serializers.CharField(write_only=True, required=True)
    
    # Location fields for flood alerts
    latitude = serializers.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        required=False,
        allow_null=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, 
        decimal_places=6, 
        required=False,
        allow_null=True
    )
    
    class Meta:
        model = User
        fields = [
            'username', 'password', 'password2', 'email',
            'first_name', 'last_name', 'latitude', 'longitude'
        ]
        extra_kwargs = {
            'first_name': {'required': False},
            'last_name': {'required': False},
        }
    
    def validate(self, attrs):
        """Validate registration data"""
        if attrs['password'] != attrs['password2']:
            raise serializers.ValidationError(
                {"password": "Password fields didn't match."}
            )
        
        # Validate location coordinates
        lat = attrs.get('latitude')
        lon = attrs.get('longitude')
        
        if lat and lon:
            if not (-90 <= float(lat) <= 90):
                raise serializers.ValidationError(
                    {"latitude": "Latitude must be between -90 and 90"}
                )
            if not (-180 <= float(lon) <= 180):
                raise serializers.ValidationError(
                    {"longitude": "Longitude must be between -180 and 180"}
                )
        
        return attrs
    
    def create(self, validated_data):
        """Create user with profile"""
        # Remove password2 and location fields
        password2 = validated_data.pop('password2', None)
        latitude = validated_data.pop('latitude', None)
        longitude = validated_data.pop('longitude', None)
        
        # Create user
        user = User.objects.create(
            username=validated_data['username'],
            email=validated_data['email'],
            first_name=validated_data.get('first_name', ''),
            last_name=validated_data.get('last_name', '')
        )
        
        user.set_password(validated_data['password'])
        user.save()
        
        # Create user profile with location
        UserProfile.objects.create(
            user=user,
            latitude=latitude,
            longitude=longitude,
            flood_alert_enabled=True,  # Enable by default
            receive_email_alerts=True,
            receive_sms_alerts=True
        )
        
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(
        required=True, 
        validators=[validate_password]
    )
    
    def validate_old_password(self, value):
        """Validate old password"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Old password is incorrect")
        return value
    
    def save(self, **kwargs):
        """Save new password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


# ===============================
# USER PROFILE SERIALIZERS
# ===============================

class UserProfileSerializer(serializers.ModelSerializer):
    """
    Serializer for UserProfile model
    """
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    email = serializers.EmailField(source='user.email', read_only=True)
    
    # Computed fields
    profile_completion = serializers.SerializerMethodField()
    has_location = serializers.SerializerMethodField()
    last_alert = serializers.SerializerMethodField()
    
    class Meta:
        model = UserProfile
        fields = [
            'id', 'user', 'username', 'email',
            'latitude', 'longitude', 
            'flood_alert_enabled', 'receive_sms_alerts', 'receive_email_alerts',
            'farm_elevation', 'distance_to_river',
            'profile_completion', 'has_location', 'last_alert',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'user', 'created_at', 'updated_at']
    
    def validate(self, data):
        """Validate profile data"""
        lat = data.get('latitude')
        lon = data.get('longitude')
        
        # If both coordinates are provided, validate them
        if lat is not None and lon is not None:
            if not (-90 <= float(lat) <= 90):
                raise serializers.ValidationError({
                    "latitude": "Latitude must be between -90 and 90"
                })
            if not (-180 <= float(lon) <= 180):
                raise serializers.ValidationError({
                    "longitude": "Longitude must be between -180 and 180"
                })
        
        # If only one coordinate is provided, it's invalid
        elif (lat is None and lon is not None) or (lat is not None and lon is None):
            raise serializers.ValidationError({
                "location": "Both latitude and longitude must be provided together"
            })
        
        return data
    
    def get_profile_completion(self, obj):
        """Calculate profile completion percentage"""
        fields_to_check = [
            'latitude', 'longitude', 
            'flood_alert_enabled', 'receive_sms_alerts', 'receive_email_alerts'
        ]
        
        completed = 0
        for field in fields_to_check:
            value = getattr(obj, field, None)
            if value is not None and value != '':
                completed += 1
        
        return int((completed / len(fields_to_check)) * 100)
    
    def get_has_location(self, obj):
        """Check if user has location data"""
        return bool(obj.latitude and obj.longitude)
    
    def get_last_alert(self, obj):
        """Get user's last flood alert"""
        from .models import FloodAlert
        
        last_alert = FloodAlert.objects.filter(user=obj.user).order_by('-calculated_at').first()
        if last_alert:
            return {
                'id': last_alert.id,
                'alert_level': last_alert.alert_level,
                'calculated_at': last_alert.calculated_at,
                'is_active': last_alert.is_active(),
            }
        return None


class UserProfileUpdateSerializer(serializers.ModelSerializer):
    """
    Serializer for updating UserProfile (partial updates allowed)
    """
    class Meta:
        model = UserProfile
        fields = [
            'latitude', 'longitude',
            'flood_alert_enabled', 'receive_sms_alerts', 'receive_email_alerts',
            'farm_elevation', 'distance_to_river'
        ]
    
    def validate(self, data):
        """Validate update data"""
        lat = data.get('latitude', self.instance.latitude if self.instance else None)
        lon = data.get('longitude', self.instance.longitude if self.instance else None)
        
        # If both coordinates are being set/updated
        if 'latitude' in data or 'longitude' in data:
            if lat is not None and lon is not None:
                if not (-90 <= float(lat) <= 90):
                    raise serializers.ValidationError({
                        "latitude": "Latitude must be between -90 and 90"
                    })
                if not (-180 <= float(lon) <= 180):
                    raise serializers.ValidationError({
                        "longitude": "Longitude must be between -180 and 180"
                    })
            elif (lat is None and lon is not None) or (lat is not None and lon is None):
                raise serializers.ValidationError({
                    "location": "Both latitude and longitude must be provided together"
                })
        
        return data


# ===============================
# FLOOD ALERT SERIALIZERS
# ===============================

class FloodAlertSerializer(serializers.ModelSerializer):
    """
    Serializer for FloodAlert model
    """
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    user_email = serializers.EmailField(source='user.email', read_only=True)
    
    # Computed fields
    is_active = serializers.SerializerMethodField()
    recommended_action = serializers.SerializerMethodField()
    urgency_color = serializers.SerializerMethodField()
    time_since_created = serializers.SerializerMethodField()
    
    class Meta:
        model = FloodAlert
        fields = [
            'id', 'user', 'username', 'user_email',
            'alert_level', 'alert_message',
            'latitude', 'longitude',
            'river_discharge', 'forecast_discharge',
            'warning_threshold', 'danger_threshold',
            'rainfall_prediction', 'upstream_alert',
            'calculated_at', 'valid_until',
            'acknowledged_by_user', 'action_taken',
            'is_active', 'recommended_action', 'urgency_color', 'time_since_created'
        ]
        read_only_fields = [
            'id', 'user', 'calculated_at', 'valid_until',
            'is_active', 'recommended_action', 'urgency_color', 'time_since_created'
        ]
    
    def get_is_active(self, obj):
        """Check if alert is still active"""
        return obj.is_active()
    
    def get_recommended_action(self, obj):
        """Get recommended action based on alert level"""
        actions = {
            'GREEN': "Continue normal operations. Monitor weather updates.",
            'ORANGE': "Move irrigation pumps and portable equipment to high ground. Secure livestock.",
            'RED': "Immediate evacuation recommended. Move to designated safe zones. Do not attempt to cross flowing water.",
        }
        return actions.get(obj.alert_level, "Check local authorities for guidance.")
    
    def get_urgency_color(self, obj):
        """Get CSS color for alert level"""
        colors = {
            'GREEN': '#10B981',  # Green-500
            'ORANGE': '#F59E0B', # Orange-500
            'RED': '#EF4444',    # Red-500
        }
        return colors.get(obj.alert_level, '#6B7280')  # Gray-500
    
    def get_time_since_created(self, obj):
        """Get human-readable time since alert was created"""
        delta = timezone.now() - obj.calculated_at
        
        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"


class FloodAlertCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating FloodAlert (used by admins or automated systems)
    """
    class Meta:
        model = FloodAlert
        fields = [
            'user', 'alert_level', 'alert_message',
            'latitude', 'longitude', 'river_discharge',
            'warning_threshold', 'danger_threshold',
            'valid_until'
        ]
    
    def validate(self, data):
        """Validate alert data"""
        # Ensure valid_until is in the future
        if 'valid_until' in data and data['valid_until'] <= timezone.now():
            raise serializers.ValidationError({
                "valid_until": "Valid until must be in the future"
            })
        
        # Ensure thresholds are logical
        if 'warning_threshold' in data and 'danger_threshold' in data:
            if data['warning_threshold'] >= data['danger_threshold']:
                raise serializers.ValidationError({
                    "thresholds": "Warning threshold must be less than danger threshold"
                })
        
        return data
    
    def create(self, validated_data):
        """Create flood alert with calculated_at timestamp"""
        validated_data['calculated_at'] = timezone.now()
        
        # If valid_until not provided, default to 3 hours from now
        if 'valid_until' not in validated_data:
            validated_data['valid_until'] = timezone.now() + timedelta(hours=3)
        
        return super().create(validated_data)


class FloodAlertAcknowledgeSerializer(serializers.Serializer):
    """
    Serializer for acknowledging flood alerts
    """
    acknowledged = serializers.BooleanField(default=True)
    action_taken = serializers.ChoiceField(
        choices=[
            ('', 'No action'),
            ('MOVED_PUMPS', 'Moved pumps to high ground'),
            ('MOVED_LIVESTOCK', 'Moved livestock'),
            ('EVACUATED', 'Started evacuation'),
            ('PREPARED', 'Made preparations'),
        ],
        required=False,
        allow_blank=True
    )
    
    def update(self, instance, validated_data):
        """Update alert acknowledgement status"""
        instance.acknowledged_by_user = validated_data.get('acknowledged', True)
        instance.action_taken = validated_data.get('action_taken', '')
        instance.save()
        return instance


# ===============================
# RIVER GAUGE SERIALIZERS
# ===============================

class RiverGaugeSerializer(serializers.ModelSerializer):
    """
    Serializer for RiverGauge model
    """
    # Computed fields
    status_display = serializers.SerializerMethodField()
    time_since_update = serializers.SerializerMethodField()
    distance_to_user = serializers.SerializerMethodField()
    
    class Meta:
        model = RiverGauge
        fields = [
            'id', 'name', 'station_code',
            'latitude', 'longitude',
            'river_name', 'nearest_city',
            'warning_level', 'danger_level',
            'is_active', 'last_updated',
            'data_source',
            'status_display', 'time_since_update', 'distance_to_user'
        ]
        read_only_fields = ['id', 'last_updated']
    
    def get_status_display(self, obj):
        """Get human-readable status"""
        return "Active" if obj.is_active else "Inactive"
    
    def get_time_since_update(self, obj):
        """Get time since last update"""
        if not obj.last_updated:
            return "Never updated"
        
        delta = timezone.now() - obj.last_updated
        
        if delta.days > 0:
            return f"{delta.days} day{'s' if delta.days > 1 else ''} ago"
        elif delta.seconds >= 3600:
            hours = delta.seconds // 3600
            return f"{hours} hour{'s' if hours > 1 else ''} ago"
        elif delta.seconds >= 60:
            minutes = delta.seconds // 60
            return f"{minutes} minute{'s' if minutes > 1 else ''} ago"
        else:
            return "Just now"
    
    def get_distance_to_user(self, obj):
        """
        Calculate distance to user (requires context)
        """
        request = self.context.get('request')
        if request and request.user.is_authenticated:
            try:
                profile = request.user.profile
                if profile.latitude and profile.longitude:
                    # Simple distance calculation (approximate)
                    # In production, use geopy or PostGIS
                    from math import radians, cos, sin, asin, sqrt
                    
                    lat1 = radians(float(profile.latitude))
                    lon1 = radians(float(profile.longitude))
                    lat2 = radians(float(obj.latitude))
                    lon2 = radians(float(obj.longitude))
                    
                    # Haversine formula
                    dlon = lon2 - lon1
                    dlat = lat2 - lat1
                    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
                    c = 2 * asin(sqrt(a))
                    r = 6371  # Radius of earth in kilometers
                    
                    distance_km = round(c * r, 1)
                    return f"{distance_km} km"
            except:
                pass
        
        return None


class RiverGaugeCreateSerializer(serializers.ModelSerializer):
    """
    Serializer for creating RiverGauge (admin only)
    """
    class Meta:
        model = RiverGauge
        fields = '__all__'
    
    def validate_station_code(self, value):
        """Ensure station code is unique"""
        if RiverGauge.objects.filter(station_code=value).exists():
            raise serializers.ValidationError(
                "A river gauge with this station code already exists"
            )
        return value


# ===============================
# NOTIFICATION SERIALIZERS
# ===============================

class FloodNotificationLogSerializer(serializers.ModelSerializer):
    """
    Serializer for FloodNotificationLog model
    """
    user = serializers.PrimaryKeyRelatedField(read_only=True)
    username = serializers.CharField(source='user.username', read_only=True)
    alert = serializers.PrimaryKeyRelatedField(read_only=True)
    alert_level = serializers.CharField(source='alert.alert_level', read_only=True)
    
    # Computed fields
    delivery_channels = serializers.SerializerMethodField()
    delivery_status_display = serializers.SerializerMethodField()
    delivery_time = serializers.SerializerMethodField()
    
    class Meta:
        model = FloodNotificationLog
        fields = [
            'id', 'user', 'username', 'alert', 'alert_level',
            'sent_via_email', 'sent_via_sms', 'sent_via_push',
            'sent_at', 'delivered_at', 'delivery_status', 'error_message',
            'delivery_channels', 'delivery_status_display', 'delivery_time'
        ]
        read_only_fields = ['id', 'sent_at']
    
    def get_delivery_channels(self, obj):
        """Get list of delivery channels used"""
        channels = []
        if obj.sent_via_email:
            channels.append('email')
        if obj.sent_via_sms:
            channels.append('sms')
        if obj.sent_via_push:
            channels.append('push')
        return channels
    
    def get_delivery_status_display(self, obj):
        """Get human-readable delivery status"""
        status_map = {
            'PENDING': 'Pending',
            'SENT': 'Sent',
            'DELIVERED': 'Delivered',
            'FAILED': 'Failed',
            'READ': 'Read'
        }
        return status_map.get(obj.delivery_status, 'Unknown')
    
    def get_delivery_time(self, obj):
        """Calculate delivery time in seconds"""
        if obj.sent_at and obj.delivered_at:
            return (obj.delivered_at - obj.sent_at).total_seconds()
        return None


# ===============================
# STATISTICS SERIALIZERS
# ===============================

class AlertStatsSerializer(serializers.Serializer):
    """
    Serializer for flood alert statistics
    """
    period_days = serializers.IntegerField()
    total_alerts = serializers.IntegerField()
    alert_counts = serializers.DictField(child=serializers.IntegerField())
    acknowledgement_rate = serializers.FloatField(min_value=0, max_value=100)
    most_common_action = serializers.CharField(allow_null=True)
    avg_response_minutes = serializers.FloatField(allow_null=True, min_value=0)
    
    def to_representation(self, instance):
        """Format the statistics for API response"""
        representation = super().to_representation(instance)
        
        # Add human-readable labels
        representation['period_label'] = f"Last {instance['period_days']} day{'s' if instance['period_days'] > 1 else ''}"
        representation['acknowledgement_rate_label'] = f"{instance['acknowledgement_rate']:.1f}%"
        
        if instance['avg_response_minutes']:
            representation['avg_response_label'] = f"{instance['avg_response_minutes']:.0f} minutes"
        
        return representation


class SystemStatsSerializer(serializers.Serializer):
    """
    Serializer for system-wide statistics
    """
    total_users = serializers.IntegerField()
    users_with_location = serializers.IntegerField()
    users_flood_enabled = serializers.IntegerField()
    
    total_alerts = serializers.IntegerField()
    active_alerts = serializers.IntegerField()
    red_alerts_24h = serializers.IntegerField()
    
    total_gauges = serializers.IntegerField()
    active_gauges = serializers.IntegerField()
    
    notifications_sent_24h = serializers.IntegerField()
    notification_success_rate = serializers.FloatField(min_value=0, max_value=100)
    
    def to_representation(self, instance):
        """Format system stats with percentages"""
        representation = super().to_representation(instance)
        
        # Calculate percentages
        if instance['total_users'] > 0:
            representation['users_with_location_pct'] = round(
                (instance['users_with_location'] / instance['total_users']) * 100, 1
            )
            representation['users_flood_enabled_pct'] = round(
                (instance['users_flood_enabled'] / instance['total_users']) * 100, 1
            )
        
        if instance['total_gauges'] > 0:
            representation['active_gauges_pct'] = round(
                (instance['active_gauges'] / instance['total_gauges']) * 100, 1
            )
        
        return representation


# ===============================
# API RESPONSE SERIALIZERS
# ===============================

class ApiResponseSerializer(serializers.Serializer):
    """
    Standard API response format
    """
    success = serializers.BooleanField()
    message = serializers.CharField()
    data = serializers.DictField(required=False)
    errors = serializers.ListField(child=serializers.DictField(), required=False)
    timestamp = serializers.DateTimeField(default=timezone.now)
    
    @classmethod
    def success_response(cls, message, data=None):
        """Create a success response"""
        return cls({
            'success': True,
            'message': message,
            'data': data or {},
            'timestamp': timezone.now()
        })
    
    @classmethod
    def error_response(cls, message, errors=None):
        """Create an error response"""
        return cls({
            'success': False,
            'message': message,
            'errors': errors or [],
            'timestamp': timezone.now()
        })


class FloodStatusResponseSerializer(serializers.Serializer):
    """
    Serializer for flood status API response
    """
    alert_level = serializers.CharField()
    alert_message = serializers.CharField()
    is_active = serializers.BooleanField()
    river_discharge = serializers.FloatField(allow_null=True)
    forecast_discharge = serializers.FloatField(allow_null=True)
    warning_threshold = serializers.FloatField()
    danger_threshold = serializers.FloatField()
    calculated_at = serializers.DateTimeField()
    valid_until = serializers.DateTimeField(allow_null=True)
    recommended_action = serializers.CharField()
    urgency_color = serializers.CharField()
    
    # Optional fields
    refreshing = serializers.BooleanField(default=False)
    river_gauge = RiverGaugeSerializer(required=False, allow_null=True)
    rainfall_prediction = serializers.FloatField(required=False, allow_null=True)


# ===============================
# VALIDATION SERIALIZERS
# ===============================

class LocationValidationSerializer(serializers.Serializer):
    """
    Serializer for location validation
    """
    latitude = serializers.DecimalField(
        max_digits=9, 
        decimal_places=6,
        required=True
    )
    longitude = serializers.DecimalField(
        max_digits=9, 
        decimal_places=6,
        required=True
    )
    
    def validate(self, data):
        """Validate coordinates"""
        lat = float(data['latitude'])
        lon = float(data['longitude'])
        
        if not (-90 <= lat <= 90):
            raise serializers.ValidationError({
                "latitude": "Latitude must be between -90 and 90"
            })
        
        if not (-180 <= lon <= 180):
            raise serializers.ValidationError({
                "longitude": "Longitude must be between -180 and 180"
            })
        
        # Validate for India (optional)
        if not (6.0 <= lat <= 38.0) or not (68.0 <= lon <= 98.0):
            raise serializers.ValidationError({
                "location": "Coordinates appear to be outside India. Please confirm."
            })
        
        return data


class NotificationTestSerializer(serializers.Serializer):
    """
    Serializer for testing notifications
    """
    channels = serializers.ListField(
        child=serializers.ChoiceField(choices=['email', 'sms', 'push']),
        default=['email']
    )
    alert_level = serializers.ChoiceField(
        choices=['GREEN', 'ORANGE', 'RED'],
        default='ORANGE'
    )
    
    def validate_channels(self, value):
        """Validate notification channels"""
        if not value:
            raise serializers.ValidationError("At least one channel must be selected")
        return value