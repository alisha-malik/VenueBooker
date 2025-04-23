from django.urls import path
from . import views, client_views, vendor_views, admin_views

app_name = 'users'

urlpatterns = [
    # General URLs (used for both clients and vendors)
    path('login/', views.user_login, name='login'),
    path('register/', views.register, name='register'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('password_reset/', views.password_reset, name='password_reset'),

    # Admin URLs
    path('admin_login/', admin_views.admin_login, name='admin_login'),
    path('admin/dashboard/', admin_views.admin_dashboard, name='admin_dashboard'),
    path('admin/user/<int:user_id>/', admin_views.admin_view_user, name='admin_view_user'),
    path('admin/user/<int:user_id>/delete/', admin_views.delete_user, name='admin_delete_user'),
    path('admin/venue/<int:venue_id>/', admin_views.admin_view_venue, name='admin_view_venue'),
    path('admin/venue/<int:venue_id>/delete/', admin_views.delete_venue, name='admin_delete_venue'),
    path('admin/clients/', admin_views.admin_manage_clients, name='admin_manage_clients'),
    path('admin/venues/', admin_views.admin_manage_venues, name='admin_manage_venues'),
    path('admin/transaction/<int:booking_id>/', admin_views.admin_view_transaction, name='admin_view_transaction'),
    path('admin/booking/<int:booking_id>/delete/', admin_views.admin_delete_booking, name='admin_delete_booking'),

    # Client URLs
    path('client/dashboard/', client_views.client_dashboard, name='client_dashboard'),
    path('client/venue/<int:venue_id>/', client_views.venue_detail, name='venue_detail'),
    path('client/venue/<int:venue_id>/book/', client_views.venue_booking, name='venue_booking'),
    path('client/bookings/', client_views.view_bookings, name='view_bookings'),
    path('client/messages/', client_views.client_messages, name='client_messages'),

    # Vendor URLs
    path('vendor/dashboard/', vendor_views.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/posting/', vendor_views.create_posting, name="posting"),
    path('vendor/venue/<int:venue_id>/edit/', vendor_views.edit_venue, name='edit_venue'),
    path('vendor/venue/<int:venue_id>/delete/', vendor_views.delete_venue, name='delete_venue'),
    path('vendor/bookings/', vendor_views.vendor_booking_history, name='vendor_bookings'),
    path('vendor/messages/', vendor_views.vendor_messages, name='vendor_messages'),
    path('vendor/chat/<int:client_id>/', vendor_views.vendor_chat, name='chat'),
    path('vendor/message/send/', vendor_views.send_message, name='vendor_send_message'),

    # Messaging URLs (used for both clients and vendors)
    path('message/vendor/<int:vendor_id>/', client_views.message_vendor, name='message_vendor'),
    path('message/send/', client_views.send_message, name='send_message'),
]