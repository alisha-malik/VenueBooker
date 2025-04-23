"""
Admin Views Module

This module contains all the view functions for admins in the VenueBooker system.
It provides system-wide oversight and management tools.

Key Functionalities:
1. System Administration
2. User Management
3. Venue Management
4. Transaction Management
5. Security & Access Control
"""

from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import check_password
from datetime import datetime, timedelta
from functools import wraps


def admin_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Check if admin exists in the database
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT admin_id, first_name, last_name, email, password 
                FROM admin 
                WHERE email = %s
            """, [email])
            admin = cursor.fetchone()
            
            # Verify password and create session if valid
            if admin and check_password(password, admin[4]):  # admin[4] is password
                request.session['admin_id'] = admin[0]
                request.session['admin_email'] = admin[3]
                request.session['admin_name'] = f"{admin[1]} {admin[2]}"  # full name from first_name and last_name
                request.session['is_admin'] = True
                
                return redirect('users:admin_dashboard')
            else:
                messages.error(request, 'Invalid admin credentials.')
                return redirect('users:admin_login')
    
    return render(request, 'users/admin/login.html')


def admin_dashboard(request):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')

    with connection.cursor() as cursor:
        # Get total number of users in the system
        cursor.execute("""
            SELECT COUNT(*) as total_users
            FROM users
        """)
        user_stats = cursor.fetchone()
        total_users = user_stats[0] if user_stats else 0

        # Get total number of active bookings
        cursor.execute("""
            SELECT COUNT(*) as total_bookings
            FROM booking
        """)
        booking_stats = cursor.fetchone()
        active_bookings = booking_stats[0] if booking_stats else 0

        # Get total number of venues in the system
        cursor.execute("""
            SELECT COUNT(*) as total_venues
            FROM venue
        """)
        venue_stats = cursor.fetchone()
        total_venues = venue_stats[0] if venue_stats else 0

        # Get recent bookings with detailed information
        cursor.execute("""
            SELECT b.booking_id, v.name as venue_name, 
                   CONCAT(u.first_name, ' ', u.last_name) as client_name,
                   b.start_date,
                   v.rate * TIMESTAMPDIFF(HOUR, b.start_date, b.end_date) as amount
            FROM booking b
            JOIN venue v ON b.venue_id = v.venue_id
            JOIN users u ON b.user_id = u.user_id
            ORDER BY b.start_date DESC
            LIMIT 10
        """)
        recent_bookings = []
        for row in cursor.fetchall():
            recent_bookings.append({
                'booking_id': row[0],
                'venue_name': row[1],
                'client_name': row[2],
                'booking_date': row[3],
                'amount': row[4]
            })

    context = {
        'total_users': total_users,
        'active_bookings': active_bookings,
        'total_venues': total_venues,
        'recent_bookings': recent_bookings
    }
    
    return render(request, 'users/admin/dashboard.html', context)

def admin_view_user(request, user_id):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')
        
    with connection.cursor() as cursor:
        # Get basic user information
        cursor.execute("""
            SELECT first_name, last_name, email, phone, user_type
            FROM users
            WHERE user_id = %s
        """, [user_id])
        user_data = cursor.fetchone()
        
        if not user_data:
            messages.error(request, 'User not found.')
            return redirect('users:admin_dashboard')
            
        user = {
            'id': user_id,
            'first_name': user_data[0],
            'last_name': user_data[1],
            'email': user_data[2],
            'phone': user_data[3],
            'user_type': user_data[4]
        }
        
        # Get user's venues if they are a vendor
        venues = []
        if user['user_type'] == 'Vendor':
            cursor.execute("""
                SELECT v.venue_id, v.name, v.status, v.rate, v.street, v.city, v.province,
                       v.postal_code, v.image_url, v.description, v.capacity,
                       GROUP_CONCAT(vc.category) as categories
                FROM venue v
                LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
                WHERE v.user_id = %s
                GROUP BY v.venue_id
                ORDER BY v.name
            """, [user_id])
            for row in cursor.fetchall():
                venues.append({
                    'id': row[0],
                    'name': row[1],
                    'status': row[2],
                    'rate': float(row[3]) if row[3] else 0.0,
                    'street': row[4],
                    'city': row[5],
                    'province': row[6],
                    'postal_code': row[7],
                    'image_url': row[8],
                    'description': row[9],
                    'capacity': row[10],
                    'categories': row[11].split(',') if row[11] else []
                })
                
        # Get venue details if viewing a specific venue
        venue_id = request.GET.get('venue_id')
        venue = None
        if venue_id:
            cursor.execute("""
                SELECT v.venue_id, v.name, v.status, v.rate, v.street, v.city, v.province,
                       v.postal_code, v.image_url, v.description, v.capacity,
                       GROUP_CONCAT(vc.category) as categories,
                       u.first_name, u.last_name, u.email, u.phone
                FROM venue v
                LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
                JOIN users u ON v.user_id = u.user_id
                WHERE v.venue_id = %s
                GROUP BY v.venue_id
            """, [venue_id])
            row = cursor.fetchone()
            if row:
                venue = {
                    'id': row[0],
                    'name': row[1],
                    'status': row[2],
                    'rate': float(row[3]) if row[3] else 0.0,
                    'street': row[4],
                    'city': row[5],
                    'province': row[6],
                    'postal_code': row[7],
                    'image_url': row[8],
                    'description': row[9],
                    'capacity': row[10],
                    'categories': row[11].split(',') if row[11] else [],
                    'owner': {
                        'name': f"{row[12]} {row[13]}",
                        'email': row[14],
                        'phone': row[15]
                    }
                }
    
    if venue:
        return render(request, 'users/admin/view_venue.html', {
            'venue': venue
        })
    else:
        return render(request, 'users/admin/view_user.html', {
            'user': user,
            'venues': venues
        })

def admin_view_venue(request, venue_id):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')

    try:
        with connection.cursor() as cursor:
            # Get venue details with owner information
            cursor.execute("""
                SELECT v.venue_id, v.name, v.description, v.image_url, v.rate, 
                       v.capacity, v.street, v.city, v.province, v.postal_code, v.status,
                       u.first_name, u.last_name, u.email, u.phone
                FROM venue v 
                JOIN users u ON v.user_id = u.user_id 
                WHERE v.venue_id = %s
            """, [venue_id])
            venue_data = cursor.fetchone()
            
            if not venue_data:
                messages.error(request, "Venue not found.")
                return redirect('users:admin_dashboard')
            
            # Get venue categories
            cursor.execute("""
                SELECT category 
                FROM venue_category 
                WHERE venue_id = %s
            """, [venue_id])
            categories = [row[0] for row in cursor.fetchall()]
            
            # Create formatted address string
            address = f"{venue_data[6]}, {venue_data[7]}, {venue_data[8]} {venue_data[9]}"
            
            venue = {
                'id': venue_data[0],
                'name': venue_data[1],
                'description': venue_data[2],
                'image_url': venue_data[3],
                'rate': float(venue_data[4]) if venue_data[4] else 0.0,
                'capacity': venue_data[5],
                'address': address,
                'status': venue_data[10],
                'owner': {
                    'first_name': venue_data[11],
                    'last_name': venue_data[12],
                    'email': venue_data[13],
                    'phone': venue_data[14]
                }
            }
            
            return render(request, 'users/admin/view_venue.html', {
                'venue': venue,
                'categories': categories
            })
            
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('users:admin_dashboard')

def delete_user(request, user_id):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')

    try:
        with connection.cursor() as cursor:
            # Verify user exists and is a client
            cursor.execute("""
                SELECT user_type 
                FROM users 
                WHERE user_id = %s
            """, [user_id])
            user_data = cursor.fetchone()
            
            if not user_data:
                messages.error(request, "User not found.")
                return redirect('users:admin_manage_clients')
            
            if user_data[0] != 'Client':
                messages.error(request, "Only client accounts can be deleted.")
                return redirect('users:admin_manage_clients')

            # Remove user's bookings
            cursor.execute("""
                DELETE FROM booking 
                WHERE user_id = %s
            """, [user_id])

            # Delete the user record
            cursor.execute("""
                DELETE FROM users 
                WHERE user_id = %s
            """, [user_id])
            
            messages.success(request, "Client account has been successfully deleted.")
            
    except Exception as e:
        messages.error(request, f"An error occurred while deleting the user: {str(e)}")
    
    return redirect('users:admin_dashboard')

def admin_manage_clients(request):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')

    with connection.cursor() as cursor:
        # Get all client users with their details
        cursor.execute("""
            SELECT user_id, first_name, last_name, email, phone, user_type
            FROM users
            WHERE user_type = 'Client'
            ORDER BY first_name, last_name
        """)
        clients = []
        for row in cursor.fetchall():
            clients.append({
                'id': row[0],
                'first_name': row[1],
                'last_name': row[2],
                'email': row[3],
                'phone': row[4],
                'user_type': row[5]
            })

    return render(request, 'users/admin/manage_clients.html', {
        'clients': clients
    })

def admin_manage_venues(request):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')

    with connection.cursor() as cursor:
        # Get all venues with owner details
        cursor.execute("""
            SELECT v.venue_id, v.name, v.status, v.rate, v.city, v.province,
                   CONCAT(u.first_name, ' ', u.last_name) as owner_name
            FROM venue v
            JOIN users u ON v.user_id = u.user_id
            ORDER BY v.name
        """)
        venues = []
        for row in cursor.fetchall():
            venues.append({
                'id': row[0],
                'name': row[1],
                'status': row[2],
                'rate': float(row[3]) if row[3] else 0.0,
                'location': f"{row[4]}, {row[5]}",
                'owner_name': row[6]
            })

    return render(request, 'users/admin/manage_venues.html', {
        'venues': venues
    })

def admin_view_transaction(request, booking_id):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')

    try:
        with connection.cursor() as cursor:
            # Get detailed booking information with venue and client details
            cursor.execute("""
                SELECT b.booking_id, b.start_date, b.end_date,
                       v.name as venue_name, v.rate,
                       CONCAT(u.first_name, ' ', u.last_name) as client_name,
                       u.email as client_email,
                       u.phone as client_phone,
                       v.rate * TIMESTAMPDIFF(HOUR, b.start_date, b.end_date) as total_amount
                FROM booking b
                JOIN venue v ON b.venue_id = v.venue_id
                JOIN users u ON b.user_id = u.user_id
                WHERE b.booking_id = %s
            """, [booking_id])
            
            booking_data = cursor.fetchone()
            
            if not booking_data:
                messages.error(request, "Transaction not found.")
                return redirect('users:admin_dashboard')
            
            # Format transaction data for display
            transaction = {
                'id': booking_data[0],
                'start_date': booking_data[1],
                'end_date': booking_data[2],
                'venue_name': booking_data[3],
                'hourly_rate': booking_data[4],
                'client_name': booking_data[5],
                'client_email': booking_data[6],
                'client_phone': booking_data[7],
                'total_amount': booking_data[8],
                'duration_hours': (booking_data[2] - booking_data[1]).total_seconds() / 3600
            }
            
            return render(request, 'users/admin/view_transaction.html', {
                'transaction': transaction
            })
            
    except Exception as e:
        messages.error(request, f"An error occurred: {str(e)}")
        return redirect('users:admin_dashboard')

def delete_venue(request, venue_id):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')

    try:
        with connection.cursor() as cursor:
            # Verify venue exists
            cursor.execute("""
                SELECT venue_id 
                FROM venue 
                WHERE venue_id = %s
            """, [venue_id])
            venue_data = cursor.fetchone()
            
            if not venue_data:
                messages.error(request, "Venue not found.")
                return redirect('users:admin_dashboard')

            # Remove venue's bookings
            cursor.execute("""
                DELETE FROM booking 
                WHERE venue_id = %s
            """, [venue_id])

            # Remove venue's categories
            cursor.execute("""
                DELETE FROM venue_category 
                WHERE venue_id = %s
            """, [venue_id])

            # Delete the venue record
            cursor.execute("""
                DELETE FROM venue 
                WHERE venue_id = %s
            """, [venue_id])
            
            messages.success(request, "Venue has been successfully deleted.")
            
    except Exception as e:
        messages.error(request, f"An error occurred while deleting the venue: {str(e)}")
    
    return redirect('users:admin_manage_venues')

def admin_delete_booking(request, booking_id):
    if not request.session.get('is_admin'):
        messages.error(request, 'Please login as an administrator.')
        return redirect('users:admin_login')

    try:
        with connection.cursor() as cursor:
            # Verify booking exists
            cursor.execute("""
                SELECT b.booking_id, v.name as venue_name
                FROM booking b
                JOIN venue v ON b.venue_id = v.venue_id
                WHERE b.booking_id = %s
            """, [booking_id])
            booking = cursor.fetchone()

            if not booking:
                messages.error(request, 'Booking not found.')
                return redirect('users:admin_dashboard')

            # Delete the booking record
            cursor.execute("""
                DELETE FROM booking
                WHERE booking_id = %s
            """, [booking_id])

            messages.success(request, f'Successfully deleted booking for {booking[1]}.')
            return redirect('users:admin_dashboard')

    except Exception as e:
        messages.error(request, f'An error occurred while deleting the booking: {str(e)}')
        return redirect('users:admin_dashboard')