from django.shortcuts import render, redirect, get_object_or_404
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from .forms import BookingForm
from datetime import datetime, timedelta
from django.contrib.auth.models import User
from django.core.mail import send_mail
from django.urls import reverse
import secrets
from django.conf import settings
import random

def register(request):
    if request.method == 'POST':
        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').lower().strip()
        password = request.POST.get('password', '')
        confirm_password = request.POST.get('confirm_password', '')
        user_type = request.POST.get('user_type', '').strip()

        # Map "Venue Owner" to "Vendor" for database compatibility
        if user_type == "Venue Owner":
            user_type = "Vendor"

        # Validate passwords match
        if password != confirm_password:
            messages.error(request, "Passwords do not match.")
            return render(request, 'users/register.html', {
                'form_data': {
                    'first_name': first_name,
                    'last_name': last_name,
                    'phone': phone,
                    'email': email,
                    'user_type': user_type
                }
            })

        with connection.cursor() as cursor:
            try:
                # Check if this exact email and user_type combination already exists
                cursor.execute("SELECT 1 FROM users WHERE email = %s AND user_type = %s", [email, user_type])
                if cursor.fetchone():
                    messages.error(request, f"This email is already registered as a {user_type}. If you forgot your password, you can reset it.")
                    return render(request, 'users/login.html', {
                        'email': email,
                        'user_type': user_type,
                        'show_forgot_password': True
                    })

                # Check if email exists with a different user type
                cursor.execute("SELECT user_type FROM users WHERE email = %s", [email])
                existing_user = cursor.fetchone()
                if existing_user:
                    messages.error(request, f"This email is already registered as a {existing_user[0]}. Please log in with your existing account.")
                    return render(request, 'users/login.html', {
                        'email': email,
                        'user_type': existing_user[0]
                    })

                # Proceed to create account (allowed if email is not registered)
                hashed_password = make_password(password)
                cursor.execute("""
                    INSERT INTO users 
                    (first_name, last_name, phone, email, user_type, password)
                    VALUES (%s, %s, %s, %s, %s, %s)
                """, [first_name, last_name, phone, email, user_type, hashed_password])

                messages.success(request, "Registration successful! Please log in.")
                return redirect('users:login')

            except Exception as e:
                messages.error(request, "Registration failed. Please try again.")
                print(f"Registration error: {str(e)}")
                return render(request, 'users/register.html', {
                    'form_data': {
                        'first_name': first_name,
                        'last_name': last_name,
                        'phone': phone,
                        'email': email,
                        'user_type': user_type
                    }
                })

    return render(request, 'users/register.html')

def user_login(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').lower().strip()
        password = request.POST.get('password', '')
        selected_type = request.POST.get('user_type', '').strip()
        
        # Map "Venue Owner" to "Vendor" for database compatibility
        if selected_type == "Venue Owner":
            selected_type = "Vendor"

        with connection.cursor() as cursor:
            try:
                # Search by email only — we want to validate the type afterward
                cursor.execute("""
                    SELECT user_id, first_name, last_name, phone, email, user_type, password
                    FROM users WHERE email = %s
                """, [email])
                row = cursor.fetchone()

                if row:
                    user_id, first_name, last_name, phone, email, actual_type, hashed_password = row

                    # Check if the user is trying to log in with the correct user type
                    if actual_type != selected_type:
                        messages.error(request, f"This email is registered as a {actual_type}. Please select the correct account type.")
                        return render(request, 'users/login.html', {
                            'email': email,
                            'user_type': actual_type
                        })

                    if check_password(password, hashed_password):
                        request.session['user_id'] = user_id
                        request.session['user_type'] = actual_type

                        # Route to the appropriate dashboard based on user type
                        if actual_type == "Client":
                            return redirect('users:client_dashboard')
                        else:  # Vendor/Venue Owner
                            return redirect('users:vendor_dashboard')
                    else:
                        messages.error(request, "Incorrect password. If you forgot your password, you can reset it.")
                        return render(request, 'users/login.html', {
                            'show_forgot_password': True,
                            'email': email,
                            'user_type': selected_type
                        })
                else:
                    messages.error(request, f"No account found with this email.")
                    return render(request, 'users/login.html', {
                        'email': email,
                        'user_type': selected_type
                    })

            except Exception as e:
                messages.error(request, "Login error occurred.")
                print(f"[DEBUG] Login error: {str(e)}")

    return render(request, 'users/login.html')

def password_reset(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        new_password1 = request.POST.get('new_password1')
        new_password2 = request.POST.get('new_password2')
        
        try:
            with connection.cursor() as cursor:
                # First check if this is an email verification request
                if not new_password1 and not new_password2:
                    # Verify email exists
                    cursor.execute("""
                        SELECT user_id, first_name, last_name, email, user_type
                        FROM users WHERE email = %s
                    """, [email])
                    user_data = cursor.fetchone()

                    if not user_data:
                        messages.error(request, "No account found with this email address.")
                        return redirect('users:password_reset')

                    # Store email and user_type in session for verification
                    request.session['reset_email'] = email
                    request.session['user_type'] = user_data[4]  # Store user_type from query result
                    messages.success(request, "Email verified. Please enter your new password.")
                    return render(request, 'users/password_reset.html', {'show_password_form': True})
                
                # This is the password update request
                stored_email = request.session.get('reset_email')
                stored_user_type = request.session.get('user_type')
                
                if not stored_email or email != stored_email:
                    messages.error(request, "Please verify your email first.")
                    return redirect('users:password_reset')
                
                # Validate passwords match
                if new_password1 != new_password2:
                    messages.error(request, "Passwords do not match.")
                    return render(request, 'users/password_reset.html', {'show_password_form': True})
                
                # Hash the new password
                hashed_password = make_password(new_password1)
                
                # Update the user's password while preserving the user_type
                cursor.execute("""
                    UPDATE users 
                    SET password = %s 
                    WHERE email = %s AND user_type = %s
                """, [hashed_password, email, stored_user_type])
                
                # Clear the session data
                del request.session['reset_email']
                del request.session['user_type']
                
                messages.success(request, "Your password has been successfully reset. Please log in with your new password.")
                return redirect('users:login')

        except Exception as e:
            print(f"[DEBUG] Password reset error: {str(e)}")
            messages.error(request, "An error occurred while processing your request.")
            return redirect('users:password_reset')
    
    # GET request - show initial password reset form
    return render(request, 'users/password_reset.html')

def profile(request):
    user_id = request.session.get('user_id')

    if not user_id:
        return redirect('users:login')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT first_name, last_name, phone, email, user_type
            FROM users WHERE user_id = %s
        """, [user_id])
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Profile data not found")
        return redirect('users:login')

    return render(request, 'users/profile.html', {
        'user': {
            'first_name': row[0],
            'last_name': row[1],
            'phone': row[2],
            'email': row[3],
            'user_type': row[4]
        }
    })

def user_logout(request):
    logout(request)
    request.session.flush()
    messages.success(request, "You have been logged out")
    return redirect('users:login')

def venue_booking(request, venue_id):
    if request.method == 'POST':
        # Get form data
        start_date = request.POST.get('start_date')
        start_time = request.POST.get('start_time')
        end_date = request.POST.get('end_date')
        end_time = request.POST.get('end_time')
        method = request.POST.get('method')
        card_number = request.POST.get('card_number')
        expiry_date = request.POST.get('expiry_date')
        cvv = request.POST.get('cvv')

        # Validate required fields
        if not all([start_date, start_time, end_date, end_time, method, card_number, expiry_date, cvv]):
            messages.error(request, 'All fields are required')
            return render(request, 'client/venue_booking.html', {
                'venue': get_object_or_404(Venue, venue_id=venue_id),
                'today': datetime.now().date(),
                'form_data': request.POST
            })

        try:
            # Convert dates and times to datetime objects
            start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
            expiry_date_obj = datetime.strptime(expiry_date, "%Y-%m").date()

            # Validate booking dates
            min_booking_date = datetime.now() + timedelta(days=5)
            if start_datetime < min_booking_date:
                messages.error(request, 'Booking must be at least 5 days in advance')
                return render(request, 'client/venue_booking.html', {
                    'venue': get_object_or_404(Venue, venue_id=venue_id),
                    'today': datetime.now().date(),
                    'form_data': request.POST
                })

            if end_datetime <= start_datetime:
                messages.error(request, 'End time must be after start time')
                return render(request, 'client/venue_booking.html', {
                    'venue': get_object_or_404(Venue, venue_id=venue_id),
                    'today': datetime.now().date(),
                    'form_data': request.POST
                })

            duration = end_datetime - start_datetime
            if duration.total_seconds() < 3600:
                messages.error(request, 'Booking duration must be at least 1 hour')
                return render(request, 'client/venue_booking.html', {
                    'venue': get_object_or_404(Venue, venue_id=venue_id),
                    'today': datetime.now().date(),
                    'form_data': request.POST
                })

            # Validate card expiry
            if expiry_date_obj < datetime.now().date():
                messages.error(request, 'Card has expired')
                return render(request, 'client/venue_booking.html', {
                    'venue': get_object_or_404(Venue, venue_id=venue_id),
                    'today': datetime.now().date(),
                    'form_data': request.POST
                })

            # Validate card number
            card_number = ''.join(filter(str.isdigit, card_number))
            if not (13 <= len(card_number) <= 19):
                messages.error(request, 'Card number must be between 13 and 19 digits')
                return render(request, 'client/venue_booking.html', {
                    'venue': get_object_or_404(Venue, venue_id=venue_id),
                    'today': datetime.now().date(),
                    'form_data': request.POST
                })

            # Validate CVV
            if not (3 <= len(cvv) <= 4):
                messages.error(request, 'CVV must be 3 or 4 digits')
                return render(request, 'client/venue_booking.html', {
                    'venue': get_object_or_404(Venue, venue_id=venue_id),
                    'today': datetime.now().date(),
                    'form_data': request.POST
                })

            # Create booking record
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO bookings 
                    (venue_id, client_id, start_datetime, end_datetime, 
                     payment_method, card_last_four, card_expiry, status)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, [
                    venue_id,
                    request.session.get('user_id'),
                    start_datetime,
                    end_datetime,
                    method,
                    card_number[-4:],
                    expiry_date,
                    'pending'
                ])

            messages.success(request, 'Booking request submitted successfully!')
            return redirect('users:client_dashboard')

        except Exception as e:
            messages.error(request, 'An error occurred while processing your booking. Please try again.')
            return render(request, 'client/venue_booking.html', {
                'venue': get_object_or_404(Venue, venue_id=venue_id),
                'today': datetime.now().date(),
                'form_data': request.POST
            })

    # GET request - show booking form
    return render(request, 'client/venue_booking.html', {
        'venue': get_object_or_404(Venue, venue_id=venue_id),
        'today': datetime.now().date()
    })

def admin_login(request):
    if request.method == 'POST':
        email = request.POST.get('email')
        password = request.POST.get('password')
        
        # Check if user exists and is an admin
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT id, email, password, is_admin 
                FROM users_user 
                WHERE email = %s
            """, [email])
            user = cursor.fetchone()
            
            if user and check_password(password, user[2]) and user[3]:  # user[3] is is_admin
                # Set session variables
                request.session['user_id'] = user[0]
                request.session['email'] = user[1]
                request.session['is_admin'] = True
                
                messages.success(request, 'Successfully logged in as admin.')
                return redirect('admin_dashboard')
            else:
                messages.error(request, 'Invalid admin credentials.')
                return redirect('admin_login')
    
    return render(request, 'users/admin_login.html')