from django.urls import path
from . import views, client_views, vendor_views

app_name = 'users'

urlpatterns = [
    path('register/', views.register, name='register'),
    path('login/', views.user_login, name='login'),
    path('logout/', views.user_logout, name='logout'),
    path('profile/', views.profile, name='profile'),
    path('forgot-password/', views.forgot_password, name='forgot_password'),

    path('client/dashboard/', client_views.client_dashboard, name='client_dashboard'),

    path('vendor/dashboard/', vendor_views.vendor_dashboard, name='vendor_dashboard'),
    path('vendor/posting', vendor_views.create_posting, name="posting"),
    path('vendor/venue/<int:venue_id>/edit/', vendor_views.edit_venue, name='edit_venue'),
    path('vendor/venue/<int:venue_id>/delete/', vendor_views.delete_venue, name='delete_posting'),
]
 