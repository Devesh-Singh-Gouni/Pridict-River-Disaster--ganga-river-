# admin.py
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.auth.models import User
from django.utils.html import format_html
from django.urls import reverse
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
# INLINE ADMIN FOR USER PROFILE
# ===============================
class UserProfileInline(admin.StackedInline):
    """
    Shows UserProfile as inline in User admin
    """
    model = UserProfile
    can_delete = False
    verbose_name_plural = 'Flood Alert Profile'
    fields = (
        'latitude', 'longitude', 
        'flood_alert_enabled', 'receive_sms_alerts', 'receive_email_alerts',
        'farm_elevation', 'distance_to_river',
        'profile_completion'
    )
    readonly_fields = ('profile_completion',)
    
    def profile_completion(self, obj):
        """Calculate profile completion percentage"""
        if not obj:
            return "0%"
        
        fields_to_check = [
            'latitude', 'longitude', 
            'flood_alert_enabled', 'receive_sms_alerts', 'receive_email_alerts'
        ]
        
        completed = 0
        for field in fields_to_check:
            value = getattr(obj, field, None)
            if value is not None and value != '':
                completed += 1
        
        percentage = (completed / len(fields_to_check)) * 100
        color = "green" if percentage >= 80 else "orange" if percentage >= 50 else "red"
        
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}%</span>',
            color,
            int(percentage)
        )
    
    profile_completion.short_description = 'Profile Completion'


# ===============================
# CUSTOM USER ADMIN
# ===============================
class UserAdmin(BaseUserAdmin):
    """
    Extends default User admin to include flood profile
    """
    inlines = (UserProfileInline,)
    list_display = (
        'username', 'email', 'first_name', 'last_name', 
        'is_staff', 'is_active', 'flood_profile_status'
    )
    list_filter = ('is_staff', 'is_active', 'profile__flood_alert_enabled')
    
    def flood_profile_status(self, obj):
        """Show flood alert status for user"""
        try:
            profile = obj.profile
            if not profile.flood_alert_enabled:
                return format_html('<span style="color: gray;">Disabled</span>')
            
            if not profile.latitude or not profile.longitude:
                return format_html('<span style="color: orange;">No Location</span>')
            
            # Get latest alert
            latest_alert = FloodAlert.objects.filter(user=obj).order_by('-calculated_at').first()
            if latest_alert:
                color_map = {
                    'GREEN': 'green',
                    'ORANGE': 'orange',
                    'RED': 'red'
                }
                return format_html(
                    '<span style="color: {}; font-weight: bold;">{}</span>',
                    color_map.get(latest_alert.alert_level, 'gray'),
                    latest_alert.alert_level
                )
            
            return format_html('<span style="color: blue;">No Alerts</span>')
        except UserProfile.DoesNotExist:
            return format_html('<span style="color: red;">No Profile</span>')
    
    flood_profile_status.short_description = 'Flood Status'


# ===============================
# FLOOD ALERT ADMIN
# ===============================
@admin.register(FloodAlert)
class FloodAlertAdmin(admin.ModelAdmin):
    """
    Admin interface for Flood Alerts
    """
    list_display = (
        'user_info', 
        'alert_level_display', 
        'location_info',
        'river_discharge', 
        'calculated_time', 
        'is_active_display',
        'acknowledged_display',
        'action_taken_display'
    )
    
    list_filter = (
        'alert_level', 
        'acknowledged_by_user', 
        'calculated_at',
        'action_taken'
    )
    
    search_fields = (
        'user__username', 
        'user__email', 
        'alert_message',
        'latitude', 
        'longitude'
    )
    
    readonly_fields = (
        'calculated_at', 
        'valid_until',
        'alert_actions',
        'related_notifications'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('user', 'alert_level', 'alert_message')
        }),
        ('Location Data', {
            'fields': ('latitude', 'longitude', 'location_info')
        }),
        ('River Data', {
            'fields': ('river_discharge', 'forecast_discharge', 'warning_threshold', 'danger_threshold')
        }),
        ('Timestamps', {
            'fields': ('calculated_at', 'valid_until', 'is_active_display')
        }),
        ('User Response', {
            'fields': ('acknowledged_by_user', 'action_taken', 'alert_actions')
        }),
        ('Related Data', {
            'fields': ('related_notifications',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['mark_as_acknowledged', 'resend_notifications', 'export_alerts']
    
    def user_info(self, obj):
        """Display user info with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a><br/><small>{}</small>',
            url,
            obj.user.username,
            obj.user.email
        )
    user_info.short_description = 'User'
    user_info.admin_order_field = 'user__username'
    
    def alert_level_display(self, obj):
        """Color-coded alert level"""
        color_map = {
            'GREEN': ('green', '✅'),
            'ORANGE': ('orange', '⚠️'),
            'RED': ('red', '🚨')
        }
        color, icon = color_map.get(obj.alert_level, ('gray', ''))
        return format_html(
            '<span style="color: {}; font-weight: bold;">{} {}</span>',
            color,
            icon,
            obj.alert_level
        )
    alert_level_display.short_description = 'Alert Level'
    
    def location_info(self, obj):
        """Display location with Google Maps link"""
        if obj.latitude and obj.longitude:
            maps_url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html(
                '<a href="{}" target="_blank">{}, {}</a>',
                maps_url,
                round(obj.latitude, 4),
                round(obj.longitude, 4)
            )
        return "No location"
    location_info.short_description = 'Location'
    
    def calculated_time(self, obj):
        """Display time with human-readable format"""
        return obj.calculated_at.strftime("%Y-%m-%d %H:%M")
    calculated_time.short_description = 'Calculated'
    calculated_time.admin_order_field = 'calculated_at'
    
    def is_active_display(self, obj):
        """Display if alert is still active"""
        if obj.is_active():
            return format_html(
                '<span style="color: green; font-weight: bold;">ACTIVE</span>'
            )
        else:
            return format_html(
                '<span style="color: gray;">EXPIRED</span>'
            )
    is_active_display.short_description = 'Status'
    
    def acknowledged_display(self, obj):
        """Display acknowledgement status"""
        if obj.acknowledged_by_user:
            return format_html(
                '<span style="color: green;">✅ Acknowledged</span>'
            )
        return format_html(
            '<span style="color: orange;">⏳ Pending</span>'
        )
    acknowledged_display.short_description = 'Acknowledged'
    
    def action_taken_display(self, obj):
        """Display action taken with icons"""
        actions_map = {
            'MOVED_PUMPS': ('🛠️', 'Moved Pumps'),
            'MOVED_LIVESTOCK': ('🐄', 'Moved Livestock'),
            'EVACUATED': ('🚨', 'Evacuated'),
            'PREPARED': ('✅', 'Prepared'),
            '': ('⏳', 'No Action')
        }
        icon, text = actions_map.get(obj.action_taken, ('❓', 'Unknown'))
        return format_html('{} {}', icon, text)
    action_taken_display.short_description = 'Action Taken'
    
    def alert_actions(self, obj):
        """Quick action buttons in detail view"""
        buttons = []
        
        if not obj.acknowledged_by_user:
            buttons.append(
                f'<a href="/admin/backend/floodalert/{obj.id}/acknowledge/" '
                f'class="button" style="background: #4CAF50; color: white; padding: 5px 10px; '
                f'border-radius: 3px; text-decoration: none;">Mark as Acknowledged</a>'
            )
        
        if obj.alert_level in ['ORANGE', 'RED']:
            buttons.append(
                f'<a href="/admin/backend/floodalert/{obj.id}/resend/" '
                f'class="button" style="background: #2196F3; color: white; padding: 5px 10px; '
                f'border-radius: 3px; text-decoration: none;">Resend Notifications</a>'
            )
        
        if buttons:
            return format_html('&nbsp;'.join(buttons))
        return "No actions available"
    alert_actions.short_description = 'Quick Actions'
    
    def related_notifications(self, obj):
        """Show related notifications"""
        notifications = obj.notifications.all()
        if notifications.exists():
            items = []
            for notif in notifications[:5]:  # Show only 5
                status_color = {
                    'DELIVERED': 'green',
                    'SENT': 'blue',
                    'FAILED': 'red',
                    'PENDING': 'orange'
                }.get(notif.delivery_status, 'gray')
                
                items.append(
                    f'<li style="margin-bottom: 5px;">'
                    f'<span style="color: {status_color}; font-weight: bold;">'
                    f'{notif.delivery_status}</span> - '
                    f'{notif.sent_at.strftime("%H:%M")} | '
                    f'Email: {"✅" if notif.sent_via_email else "❌"} '
                    f'SMS: {"✅" if notif.sent_via_sms else "❌"}'
                    f'</li>'
                )
            
            return format_html(
                '<ul style="margin: 0; padding-left: 20px;">{}</ul>'
                '<br><small>Total: {}</small>',
                ''.join(items),
                notifications.count()
            )
        return "No notifications sent"
    related_notifications.short_description = 'Notifications'
    
    # Custom Actions
    def mark_as_acknowledged(self, request, queryset):
        """Mark selected alerts as acknowledged"""
        updated = queryset.update(acknowledged_by_user=True)
        self.message_user(
            request, 
            f"Successfully marked {updated} alert(s) as acknowledged."
        )
    mark_as_acknowledged.short_description = "✅ Mark selected as acknowledged"
    
    def resend_notifications(self, request, queryset):
        """Resend notifications for selected alerts"""
        from .tasks import send_flood_notifications
        count = 0
        for alert in queryset:
            if alert.alert_level in ['ORANGE', 'RED']:
                send_flood_notifications.delay(alert.user, alert)
                count += 1
        
        self.message_user(
            request,
            f"Queued {count} alert(s) for notification resend."
        )
    resend_notifications.short_description = "📨 Resend notifications"
    
    def export_alerts(self, request, queryset):
        """Export selected alerts to CSV"""
        import csv
        from django.http import HttpResponse
        
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="flood_alerts_export.csv"'
        
        writer = csv.writer(response)
        writer.writerow([
            'User', 'Email', 'Alert Level', 'Location', 
            'Discharge (m³/s)', 'Calculated At', 'Valid Until',
            'Acknowledged', 'Action Taken', 'Message'
        ])
        
        for alert in queryset:
            writer.writerow([
                alert.user.username,
                alert.user.email,
                alert.alert_level,
                f"{alert.latitude}, {alert.longitude}",
                alert.river_discharge,
                alert.calculated_at,
                alert.valid_until,
                "Yes" if alert.acknowledged_by_user else "No",
                alert.action_taken,
                alert.alert_message[:100]  # First 100 chars
            ])
        
        return response
    export_alerts.short_description = "📊 Export to CSV"
    
    # Custom change view URL handlers
    def get_urls(self):
        """Add custom URLs for alert actions"""
        from django.urls import path
        
        urls = super().get_urls()
        custom_urls = [
            path(
                '<path:object_id>/acknowledge/',
                self.admin_site.admin_view(self.acknowledge_alert),
                name='floodalert_acknowledge'
            ),
            path(
                '<path:object_id>/resend/',
                self.admin_site.admin_view(self.resend_alert_notifications),
                name='floodalert_resend'
            ),
        ]
        return custom_urls + urls
    
    def acknowledge_alert(self, request, object_id):
        """Handle alert acknowledgement from admin"""
        from django.shortcuts import redirect
        
        alert = self.get_object(request, object_id)
        alert.acknowledged_by_user = True
        alert.save()
        
        self.message_user(request, f"Alert for {alert.user.username} marked as acknowledged.")
        return redirect('admin:backend_floodalert_changelist')
    
    def resend_alert_notifications(self, request, object_id):
        """Handle notification resend from admin"""
        from django.shortcuts import redirect
        from .tasks import send_flood_notifications
        
        alert = self.get_object(request, object_id)
        if alert.alert_level in ['ORANGE', 'RED']:
            send_flood_notifications.delay(alert.user, alert)
            self.message_user(request, f"Notifications for {alert.user.username} queued for resend.")
        else:
            self.message_user(request, "Only ORANGE and RED alerts can have notifications resent.", level='warning')
        
        return redirect('admin:backend_floodalert_change', object_id)


# ===============================
# USER PROFILE ADMIN
# ===============================
@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    """
    Admin interface for User Profiles
    """
    list_display = (
        'user_info',
        'location_display',
        'flood_alerts_status',
        'notification_preferences',
        'profile_updated'
    )
    
    list_filter = (
        'flood_alert_enabled',
        'receive_sms_alerts',
        'receive_email_alerts',
        'created_at'
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'latitude',
        'longitude'
    )
    
    readonly_fields = (
        'user_info_display',
        'recent_alerts',
        'profile_created',
        'profile_updated'
    )
    
    fieldsets = (
        ('User Information', {
            'fields': ('user_info_display', 'user')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'location_map')
        }),
        ('Flood Risk Factors', {
            'fields': ('farm_elevation', 'distance_to_river'),
            'classes': ('collapse',)
        }),
        ('Alert Preferences', {
            'fields': (
                'flood_alert_enabled', 
                'receive_sms_alerts', 
                'receive_email_alerts'
            )
        }),
        ('Recent Activity', {
            'fields': ('recent_alerts', 'profile_created', 'profile_updated'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['enable_alerts', 'disable_alerts', 'test_notifications']
    
    def user_info(self, obj):
        """Display user with link"""
        url = reverse('admin:auth_user_change', args=[obj.user.id])
        return format_html(
            '<a href="{}">{}</a><br/><small>{}</small>',
            url,
            obj.user.username,
            obj.user.email
        )
    user_info.short_description = 'User'
    
    def user_info_display(self, obj):
        """Display user info in detail view"""
        return format_html(
            '<strong>Username:</strong> {}<br>'
            '<strong>Email:</strong> {}<br>'
            '<strong>Joined:</strong> {}',
            obj.user.username,
            obj.user.email,
            obj.user.date_joined.strftime("%Y-%m-%d %H:%M")
        )
    user_info_display.short_description = 'User Information'
    
    def location_display(self, obj):
        """Display location with map link"""
        if obj.latitude and obj.longitude:
            maps_url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
            return format_html(
                '<a href="{}" target="_blank">📍 {}, {}</a>',
                maps_url,
                round(obj.latitude, 4),
                round(obj.longitude, 4)
            )
        return format_html('<span style="color: orange;">📍 No location</span>')
    location_display.short_description = 'Location'
    
    def location_map(self, obj):
        """Show embedded Google Map in detail view"""
        if obj.latitude and obj.longitude:
            return format_html(
                '<iframe width="100%" height="200" frameborder="0" style="border:0" '
                'src="https://www.google.com/maps/embed/v1/view?key=AIzaSyB7EXAMPLEKEY&'
                'center={},{}&zoom=12&maptype=roadmap" allowfullscreen></iframe>',
                obj.latitude,
                obj.longitude
            )
        return "Location not set"
    location_map.short_description = 'Map View'
    
    def flood_alerts_status(self, obj):
        """Show flood alert status"""
        if not obj.flood_alert_enabled:
            return format_html('<span style="color: gray;">❌ Disabled</span>')
        
        if not obj.latitude or not obj.longitude:
            return format_html('<span style="color: orange;">⚠️ No Location</span>')
        
        # Get latest alert
        latest_alert = FloodAlert.objects.filter(user=obj.user).order_by('-calculated_at').first()
        if latest_alert:
            color_map = {'GREEN': 'green', 'ORANGE': 'orange', 'RED': 'red'}
            color = color_map.get(latest_alert.alert_level, 'gray')
            return format_html(
                '<span style="color: {};">{}</span><br><small>{}</small>',
                color,
                latest_alert.alert_level,
                latest_alert.calculated_at.strftime("%H:%M")
            )
        
        return format_html('<span style="color: blue;">✅ No Alerts</span>')
    flood_alerts_status.short_description = 'Alert Status'
    
    def notification_preferences(self, obj):
        """Show notification preferences"""
        email_icon = "✅" if obj.receive_email_alerts else "❌"
        sms_icon = "✅" if obj.receive_sms_alerts else "❌"
        
        return format_html(
            'Email: {}<br>SMS: {}',
            email_icon,
            sms_icon
        )
    notification_preferences.short_description = 'Notifications'
    
    def profile_updated(self, obj):
        """Show when profile was last updated"""
        return obj.updated_at.strftime("%Y-%m-%d %H:%M")
    profile_updated.short_description = 'Last Updated'
    profile_updated.admin_order_field = 'updated_at'
    
    def recent_alerts(self, obj):
        """Show recent alerts in detail view"""
        alerts = FloodAlert.objects.filter(user=obj.user).order_by('-calculated_at')[:5]
        
        if alerts.exists():
            items = []
            for alert in alerts:
                color_map = {'GREEN': 'green', 'ORANGE': 'orange', 'RED': 'red'}
                color = color_map.get(alert.alert_level, 'gray')
                
                items.append(
                    f'<li style="margin-bottom: 5px;">'
                    f'<span style="color: {color}; font-weight: bold;">'
                    f'{alert.alert_level}</span> - '
                    f'{alert.calculated_at.strftime("%Y-%m-%d %H:%M")}<br>'
                    f'<small>{alert.alert_message[:50]}...</small>'
                    f'</li>'
                )
            
            return format_html(
                '<ul style="margin: 0; padding-left: 20px;">{}</ul>',
                ''.join(items)
            )
        return "No alerts found"
    recent_alerts.short_description = 'Recent Alerts (Last 5)'
    
    # Custom Actions
    def enable_alerts(self, request, queryset):
        """Enable flood alerts for selected profiles"""
        updated = queryset.update(flood_alert_enabled=True)
        self.message_user(request, f"Enabled flood alerts for {updated} user(s).")
    enable_alerts.short_description = "✅ Enable flood alerts"
    
    def disable_alerts(self, request, queryset):
        """Disable flood alerts for selected profiles"""
        updated = queryset.update(flood_alert_enabled=False)
        self.message_user(request, f"Disabled flood alerts for {updated} user(s).")
    disable_alerts.short_description = "❌ Disable flood alerts"
    
    def test_notifications(self, request, queryset):
        """Send test notifications to selected users"""
        from .tasks import send_test_notification
        count = 0
        for profile in queryset:
            if profile.user.email:
                send_test_notification.delay(profile.user.id)
                count += 1
        
        self.message_user(
            request, 
            f"Test notifications queued for {count} user(s)."
        )
    test_notifications.short_description = "📧 Send test notifications"


# ===============================
# RIVER GAUGE ADMIN
# ===============================
@admin.register(RiverGauge)
class RiverGaugeAdmin(admin.ModelAdmin):
    """
    Admin interface for River Gauges
    """
    list_display = (
        'name_display',
        'river_info',
        'location_display',
        'thresholds_display',
        'status_display',
        'last_updated_display'
    )
    
    list_filter = (
        'is_active',
        'river_name',
        'data_source'
    )
    
    search_fields = (
        'name',
        'station_code',
        'river_name',
        'nearest_city'
    )
    
    readonly_fields = (
        'last_updated_display',
        'location_map',
        'gauge_stats'
    )
    
    fieldsets = (
        ('Basic Information', {
            'fields': ('name', 'station_code', 'river_name', 'nearest_city')
        }),
        ('Location', {
            'fields': ('latitude', 'longitude', 'location_map')
        }),
        ('Alert Thresholds', {
            'fields': ('warning_level', 'danger_level')
        }),
        ('Status', {
            'fields': ('is_active', 'data_source', 'last_updated_display')
        }),
        ('Statistics', {
            'fields': ('gauge_stats',),
            'classes': ('collapse',)
        })
    )
    
    actions = ['activate_gauges', 'deactivate_gauges', 'update_thresholds']
    
    def name_display(self, obj):
        """Display gauge name with status"""
        status = "✅" if obj.is_active else "❌"
        return format_html(
            '{} {}<br><small>Code: {}</small>',
            status,
            obj.name,
            obj.station_code
        )
    name_display.short_description = 'Gauge'
    
    def river_info(self, obj):
        """Display river information"""
        return format_html(
            '{}<br><small>Near: {}</small>',
            obj.river_name,
            obj.nearest_city
        )
    river_info.short_description = 'River'
    
    def location_display(self, obj):
        """Display location with map link"""
        maps_url = f"https://www.google.com/maps?q={obj.latitude},{obj.longitude}"
        return format_html(
            '<a href="{}" target="_blank">📍 {}, {}</a>',
            maps_url,
            round(obj.latitude, 4),
            round(obj.longitude, 4)
        )
    location_display.short_description = 'Location'
    
    def location_map(self, obj):
        """Show embedded map in detail view"""
        return format_html(
            '<iframe width="100%" height="200" frameborder="0" style="border:0" '
            'src="https://www.google.com/maps/embed/v1/view?key=AIzaSyB7EXAMPLEKEY&'
            'center={},{}&zoom=12&maptype=roadmap" allowfullscreen></iframe>',
            obj.latitude,
            obj.longitude
        )
    location_map.short_description = 'Map View'
    
    def thresholds_display(self, obj):
        """Display warning and danger thresholds"""
        return format_html(
            '⚠️ {}m<br>🚨 {}m',
            obj.warning_level,
            obj.danger_level
        )
    thresholds_display.short_description = 'Thresholds'
    
    def status_display(self, obj):
        """Display active status"""
        if obj.is_active:
            return format_html(
                '<span style="color: green; font-weight: bold;">ACTIVE</span>'
            )
        return format_html(
            '<span style="color: red;">INACTIVE</span>'
        )
    status_display.short_description = 'Status'
    
    def last_updated_display(self, obj):
        """Display last updated time"""
        if obj.last_updated:
            time_diff = timezone.now() - obj.last_updated
            if time_diff < timedelta(hours=1):
                color = "green"
            elif time_diff < timedelta(hours=24):
                color = "orange"
            else:
                color = "red"
            
            return format_html(
                '<span style="color: {};">{} ago</span>',
                color,
                self._humanize_time(time_diff)
            )
        return format_html('<span style="color: gray;">Never</span>')
    last_updated_display.short_description = 'Last Updated'
    
    def gauge_stats(self, obj):
        """Show gauge statistics"""
        # Count alerts near this gauge
        recent_alerts = FloodAlert.objects.filter(
            latitude__range=(obj.latitude - 0.5, obj.latitude + 0.5),
            longitude__range=(obj.longitude - 0.5, obj.longitude + 0.5),
            calculated_at__gte=timezone.now() - timedelta(days=30)
        )
        
        red_alerts = recent_alerts.filter(alert_level='RED').count()
        orange_alerts = recent_alerts.filter(alert_level='ORANGE').count()
        
        return format_html(
            '<strong>Last 30 Days:</strong><br>'
            '🚨 Red Alerts: {}<br>'
            '⚠️ Orange Alerts: {}<br>'
            '✅ Total Alerts: {}<br><br>'
            '<small>Within 50km radius</small>',
            red_alerts,
            orange_alerts,
            recent_alerts.count()
        )
    gauge_stats.short_description = 'Statistics'
    
    def _humanize_time(self, time_diff):
        """Convert timedelta to human readable format"""
        days = time_diff.days
        hours = time_diff.seconds // 3600
        minutes = (time_diff.seconds % 3600) // 60
        
        if days > 0:
            return f"{days}d {hours}h"
        elif hours > 0:
            return f"{hours}h {minutes}m"
        else:
            return f"{minutes}m"
    
    # Custom Actions
    def activate_gauges(self, request, queryset):
        """Activate selected gauges"""
        updated = queryset.update(is_active=True, last_updated=timezone.now())
        self.message_user(request, f"Activated {updated} gauge(s).")
    activate_gauges.short_description = "✅ Activate selected"
    
    def deactivate_gauges(self, request, queryset):
        """Deactivate selected gauges"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f"Deactivated {updated} gauge(s).")
    deactivate_gauges.short_description = "❌ Deactivate selected"
    
    def update_thresholds(self, request, queryset):
        """Update thresholds for selected gauges"""
        # This would typically call an API to get latest thresholds
        for gauge in queryset:
            gauge.last_updated = timezone.now()
            gauge.save()
        
        self.message_user(
            request, 
            f"Updated timestamps for {queryset.count()} gauge(s)."
        )
    update_thresholds.short_description = "🔄 Update thresholds"


# ===============================
# NOTIFICATION LOG ADMIN
# ===============================
@admin.register(FloodNotificationLog)
class FloodNotificationLogAdmin(admin.ModelAdmin):
    """
    Admin interface for Notification Logs
    """
    list_display = (
        'user_info',
        'alert_info',
        'delivery_channels',
        'delivery_status_display',
        'sent_time',
        'delivered_time'
    )
    
    list_filter = (
        'delivery_status',
        'sent_via_email',
        'sent_via_sms',
        'sent_via_push',
        'sent_at'
    )
    
    search_fields = (
        'user__username',
        'user__email',
        'alert__alert_message',
        'error_message'
    )
    
    readonly_fields = (
        'user_info_display',
        'alert_info_display',
        'delivery_details',
        'error_details'
    )
    
    fieldsets = (
        ('User Information', {
            'fields': ('user_info_display', 'user', 'alert')
        }),
        ('Delivery Information', {
            'fields': (
                'delivery_channels_display',
                'delivery_status',
                'sent_at',
                'delivered_at'
            )
        }),
        ('Details', {
            'fields': ('delivery_details', 'error_details'),
            'classes': ('collapse',)
        })
    )
    
    actions = ['retry_failed', 'mark_as_delivered']
    
    def user_info(self, obj):
        """Display user info"""
        if obj.user:
            url = reverse('admin:auth_user_change', args=[obj.user.id])
            return format_html(
                '<a href="{}">{}</a>',
                url,
                obj.user.username
            )
        return "Unknown User"
    user_info.short_description = 'User'
    
    def user_info_display(self, obj):
        """Display user info in detail view"""
        if obj.user:
            return format_html(
                '<strong>Username:</strong> {}<br>'
                '<strong>Email:</strong> {}',
                obj.user.username,
                obj.user.email
            )
        return "No user associated"
    user_info_display.short_description = 'User Details'
    
    def alert_info(self, obj):
        """Display alert info"""
        if obj.alert:
            color_map = {'GREEN': 'green', 'ORANGE': 'orange', 'RED': 'red'}
            color = color_map.get(obj.alert.alert_level, 'gray')
            return format_html(
                '<span style="color: {};">{}</span><br>'
                '<small>{}</small>',
                color,
                obj.alert.alert_level,
                obj.alert.calculated_at.strftime("%H:%M")
            )
        return "No Alert"
    alert_info.short_description = 'Alert'
    
    def alert_info_display(self, obj):
        """Display alert info in detail view"""
        if obj.alert:
            return format_html(
                '<strong>Alert Level:</strong> {}<br>'
                '<strong>Message:</strong> {}<br>'
                '<strong>Time:</strong> {}',
                obj.alert.alert_level,
                obj.alert.alert_message[:100],
                obj.alert.calculated_at.strftime("%Y-%m-%d %H:%M:%S")
            )
        return "No alert associated"
    alert_info_display.short_description = 'Alert Details'
    
    def delivery_channels(self, obj):
        """Display delivery channels"""
        channels = []
        if obj.sent_via_email:
            channels.append('📧')
        if obj.sent_via_sms:
            channels.append('📱')
        if obj.sent_via_push:
            channels.append('📲')
        
        return format_html(' '.join(channels) if channels else '❌')
    delivery_channels.short_description = 'Channels'
    
    def delivery_channels_display(self, obj):
        """Display delivery channels in detail view"""
        channels = []
        if obj.sent_via_email:
            channels.append('📧 Email')
        if obj.sent_via_sms:
            channels.append('📱 SMS')
        if obj.sent_via_push:
            channels.append('📲 Push')
        
        return format_html('<br>'.join(channels) if channels else 'No channels')
    delivery_channels_display.short_description = 'Delivery Channels'
    
    def delivery_status_display(self, obj):
        """Color-coded delivery status"""
        color_map = {
            'DELIVERED': 'green',
            'SENT': 'blue',
            'FAILED': 'red',
            'PENDING': 'orange',
            'READ': 'purple'
        }
        color = color_map.get(obj.delivery_status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.delivery_status
        )
    delivery_status_display.short_description = 'Status'
    
    def sent_time(self, obj):
        """Display sent time"""
        return obj.sent_at.strftime("%H:%M")
    sent_time.short_description = 'Sent'
    sent_time.admin_order_field = 'sent_at'
    
    def delivered_time(self, obj):
        """Display delivered time"""
        if obj.delivered_at:
            return obj.delivered_at.strftime("%H:%M")
        return "—"
    delivered_time.short_description = 'Delivered'
    
    def delivery_details(self, obj):
        """Show delivery details"""
        details = []
        
        if obj.sent_at:
            details.append(f"<strong>Sent At:</strong> {obj.sent_at.strftime('%Y-%m-%d %H:%M:%S')}")
        
        if obj.delivered_at:
            details.append(f"<strong>Delivered At:</strong> {obj.delivered_at.strftime('%Y-%m-%d %H:%M:%S')}")
            
            # Calculate delivery time
            delivery_time = obj.delivered_at - obj.sent_at
            details.append(f"<strong>Delivery Time:</strong> {delivery_time.total_seconds():.1f} seconds")
        
        details.append(f"<strong>Status:</strong> {obj.delivery_status}")
        
        return format_html('<br>'.join(details))
    delivery_details.short_description = 'Delivery Information'
    
    def error_details(self, obj):
        """Show error details if any"""
        if obj.error_message:
            return format_html(
                '<div style="background: #ffebee; padding: 10px; border-radius: 5px;">'
                '<strong>Error:</strong><br>'
                '<code style="color: #c62828;">{}</code>'
                '</div>',
                obj.error_message
            )
        return "No errors"
    error_details.short_description = 'Error Information'
    
    # Custom Actions
    def retry_failed(self, request, queryset):
        """Retry failed notifications"""
        failed = queryset.filter(delivery_status='FAILED')
        count = 0
        
        for notification in failed:
            # Here you would implement retry logic
            # For now, just mark as pending
            notification.delivery_status = 'PENDING'
            notification.save()
            count += 1
        
        self.message_user(
            request,
            f"Marked {count} failed notification(s) for retry."
        )
    retry_failed.short_description = "🔄 Retry failed notifications"
    
    def mark_as_delivered(self, request, queryset):
        """Manually mark as delivered"""
        updated = queryset.update(
            delivery_status='DELIVERED',
            delivered_at=timezone.now()
        )
        self.message_user(
            request,
            f"Marked {updated} notification(s) as delivered."
        )
    mark_as_delivered.short_description = "✅ Mark as delivered"


# ===============================
# REGISTER CUSTOM USER ADMIN
# ===============================
# Unregister default User admin
admin.site.unregister(User)

# Register with our custom admin
admin.site.register(User, UserAdmin)

# ===============================
# ADMIN SITE CUSTOMIZATION
# ===============================
admin.site.site_header = "🌊 Eco Harvest Sentinel - Flood Alert System"
admin.site.site_title = "Flood Alert Admin"
admin.site.index_title = "Welcome to Flood Alert Administration"

# Optional: Add custom admin views
class FloodAlertDashboard(admin.AdminSite):
    site_header = "Flood Alert Dashboard"
    site_title = "Flood Alert System"
    index_title = "Dashboard"
    
    def get_urls(self):
        urls = super().get_urls()
        from django.urls import path
        
        custom_urls = [
            path('dashboard/', self.admin_view(self.dashboard_view), name='dashboard'),
        ]
        return custom_urls + urls
    
    def dashboard_view(self, request):
        from django.shortcuts import render
        
        # Get dashboard statistics
        total_users = User.objects.count()
        active_alerts = FloodAlert.objects.filter(
            Q(valid_until__gte=timezone.now()) | Q(valid_until__isnull=True),
            alert_level__in=['RED', 'ORANGE']
        ).count()
        
        recent_alerts = FloodAlert.objects.filter(
            calculated_at__gte=timezone.now() - timedelta(hours=24)
        ).count()
        
        context = {
            'total_users': total_users,
            'active_alerts': active_alerts,
            'recent_alerts': recent_alerts,
        }
        
        return render(request, 'admin/dashboard.html', context)