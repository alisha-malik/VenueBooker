"""
Client Views Module

Contains all the view functions for clients in the VenueBooker system.
It handles client authentication, venue browsing, booking management, and communication with vendors.

Key Functionalities:
1. Authentication & Session Management
2. Venue Management
3. Booking Operations
4. Communication
5. Notifications
"""

from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
import sys
from django.core.mail import send_mail
from django.conf import settings
from django.http import JsonResponse

def send_and_log_notification(cursor, email_type, to_email, user_name, venue_name, booking_id, venue_id, user_id, payment_id=None, start_dt=None, end_dt=None):
    # Create email based on type
    if email_type == "Booking Confirmation":
        subject = "Venue Booking Confirmation"
        message = (
            f"Hi {user_name},\n\n"
            f"Your booking for '{venue_name}' is confirmed!\n"
            f"Start: {start_dt.strftime('%Y-%m-%d %H:%M')}\n"
            f"End: {end_dt.strftime('%Y-%m-%d %H:%M')}\n\n"
            "Thank you for using VenueBooker!"
        )
    elif email_type == "Reminder":
        subject = "Upcoming Booking Reminder"
        message = (
            f"Hi {user_name},\n\n"
            f"This is a reminder of your upcoming booking at '{venue_name}'.\n"
            f"Start: {start_dt.strftime('%Y-%m-%d %H:%M')}\n"
            f"End: {end_dt.strftime('%Y-%m-%d %H:%M')}\n\n"
            "We look forward to seeing you!"
        )
    elif email_type == "Cancellation":
        subject = "Venue Booking Cancellation"
        message = (
            f"Hi {user_name},\n\n"
            f"Your booking for '{venue_name}' has been successfully cancelled.\n\n"
            "We hope to see you again soon!"
        )
    else:
        return

    # Send the email
    send_mail(
        subject,
        message,
        settings.DEFAULT_FROM_EMAIL,
        [to_email],
        fail_silently=False
    )

    # Store the notification in the database
    cursor.execute("""
        INSERT INTO notification (booking_id, venue_id, user_id, payment_id, notification_type)
        VALUES (%s, %s, %s, %s, %s)
    """, [booking_id, venue_id, user_id, payment_id, email_type])

def send_upcoming_booking_reminders():
    now = timezone.now()
    reminder_window_start = now + timedelta(days=2)
    reminder_window_end = reminder_window_start + timedelta(days=1)

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT b.booking_id, b.start_date, b.end_date, b.venue_id, v.name,
                   u.user_id, u.first_name, u.last_name, u.email, b.payment_id
            FROM booking b
            JOIN venue v ON b.venue_id = v.venue_id
            JOIN users u ON b.user_id = u.user_id
            WHERE b.start_date BETWEEN %s AND %s
        """, [reminder_window_start, reminder_window_end])

        for row in cursor.fetchall():
            booking_id, start_dt, end_dt, venue_id, venue_name, user_id, first, last, email, payment_id = row
            user_name = f"{first} {last}"

            send_and_log_notification(
                cursor,
                email_type="Reminder",
                to_email=email,
                user_name=user_name,
                venue_name=venue_name,
                booking_id=booking_id,
                venue_id=venue_id,
                user_id=user_id,
                payment_id=payment_id,
                start_dt=start_dt,
                end_dt=end_dt
            )
        
def get_active_conversations(cursor, user_id):
    # Get active conversations for the client
    cursor.execute("""
        SELECT DISTINCT 
            u.user_id as vendor_id,
            u.first_name,
            u.last_name,
            u.email,
            (
                SELECT content 
                FROM message 
                WHERE (sender_id = %s AND receiver_id = u.user_id)
                   OR (sender_id = u.user_id AND receiver_id = %s)
                ORDER BY date_sent DESC
                LIMIT 1
            ) as last_message,
            (
                SELECT date_sent 
                FROM message 
                WHERE (sender_id = %s AND receiver_id = u.user_id)
                   OR (sender_id = u.user_id AND receiver_id = %s)
                ORDER BY date_sent DESC
                LIMIT 1
            ) as last_message_date
        FROM message m
        JOIN users u ON (
            (m.sender_id = %s AND m.receiver_id = u.user_id)
            OR (m.sender_id = u.user_id AND m.receiver_id = %s)
        )
        WHERE u.user_type = 'Vendor'
        GROUP BY u.user_id
        ORDER BY last_message_date DESC
        LIMIT 5
    """, [user_id, user_id, user_id, user_id, user_id, user_id])
    
    conversations = []
    for row in cursor.fetchall():
        conversations.append({
            'vendor_id': row[0],
            'vendor_name': f"{row[1]} {row[2]}",
            'vendor_email': row[3],
            'last_message': row[4],
            'last_message_date': row[5]
        })
    return conversations

def client_dashboard(request):
    # Verify user authentication by checking session
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Please log in to access the dashboard.")
        return redirect('users:login')

    # Initialize filter parameters from GET request for venue search
    search_query = request.GET.get('venue_name', '').strip()
    categories = request.GET.getlist('categories')  # Handle multiple categories
    province = request.GET.get('province', '').strip()
    city = request.GET.get('city', '').strip()
    street = request.GET.get('street', '').strip()
    status = request.GET.get('status', 'Active').strip()  # Default to Active venues
    rate = request.GET.get('rate', '').strip()  # Max hourly rate
    availability_type = request.GET.get('availability_type', '').strip()

    # Build base SQL query to fetch venue information with LEFT JOIN for categories
    base_query = """
        SELECT DISTINCT v.venue_id, v.name, v.rate, v.capacity, v.street, v.city, v.province, 
               v.postal_code, v.image_url, v.description, v.status,
               GROUP_CONCAT(DISTINCT vc.category SEPARATOR ',') as categories,
               ANY_VALUE(vc.availability_type) as availability_type
        FROM venue v
        LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
        WHERE 1=1
    """
    query_params = []

    # Add WHERE clauses based on provided filters
    if search_query:
        base_query += " AND (v.name LIKE %s OR v.description LIKE %s)"
        query_params.extend([f'%{search_query}%', f'%{search_query}%'])
    
    if categories:
        # Handle multiple categories using EXISTS
        category_conditions = []
        for category in categories:
            category_conditions.append("EXISTS (SELECT 1 FROM venue_category vc2 WHERE vc2.venue_id = v.venue_id AND vc2.category = %s)")
            query_params.append(category)
        base_query += " AND (" + " OR ".join(category_conditions) + ")"
    
    if province:
        base_query += " AND v.province = %s"
        query_params.append(province)
    
    if city:
        base_query += " AND v.city LIKE %s"
        query_params.append(f'%{city}%')
    
    if street:
        base_query += " AND v.street LIKE %s"
        query_params.append(f'%{street}%')
    
    if status:
        base_query += " AND v.status = %s"
        query_params.append(status)
    
    if rate:
        try:
            max_rate = float(rate)
            base_query += " AND v.rate <= %s"
            query_params.append(max_rate)
        except ValueError:
            pass  # Invalid rate value, ignore filter

    # Group results by venue and order by name
    base_query += """
        GROUP BY v.venue_id, v.name, v.rate, v.capacity, v.street, v.city, 
                 v.province, v.postal_code, v.image_url, v.description, v.status
        ORDER BY v.name ASC
    """

    # Execute the main venue query and process results
    with connection.cursor() as cursor:
        try:
            cursor.execute(base_query, query_params)
            venues = []
            
            for row in cursor.fetchall():
                # Format image URL to ensure proper serving
                image_url = row[8]
                if image_url and not image_url.startswith('/media/'):
                    image_url = f'/media/{image_url}'

                # Create venue dictionary with formatted data
                venue = {
                    'id': row[0],
                    'name': row[1],
                    'rate': float(row[2]) if row[2] else 0.0,
                    'capacity': row[3],
                    'street': row[4],
                    'city': row[5],
                    'province': row[6],
                    'postal_code': row[7],
                    'image_url': image_url,
                    'description': row[9],
                    'status': row[10],
                    'categories': row[11].split(',') if row[11] else [],
                    'availability': row[12] if row[12] else 'Full-Year'
                }
                venues.append(venue)
        except Exception as e:
            venues = []

    # Get active conversations for the user
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT 
                CASE 
                    WHEN m.sender_id = %s THEN m.receiver_id
                    ELSE m.sender_id
                END as other_user_id,
                MAX(u.first_name) as first_name,
                MAX(u.last_name) as last_name,
                MAX(u.email) as email,
                (
                    SELECT content 
                    FROM message 
                    WHERE (sender_id = %s AND receiver_id = other_user_id)
                       OR (sender_id = other_user_id AND receiver_id = %s)
                    ORDER BY date_sent DESC
                    LIMIT 1
                ) as last_message,
                (
                    SELECT date_sent 
                    FROM message 
                    WHERE (sender_id = %s AND receiver_id = other_user_id)
                       OR (sender_id = other_user_id AND receiver_id = %s)
                    ORDER BY date_sent DESC
                    LIMIT 1
                ) as last_message_date
            FROM message m
            JOIN users u ON (
                CASE 
                    WHEN m.sender_id = %s THEN m.receiver_id
                    ELSE m.sender_id
                END = u.user_id
            )
            WHERE m.sender_id = %s OR m.receiver_id = %s
            GROUP BY other_user_id
            ORDER BY last_message_date DESC
        """, [user_id, user_id, user_id, user_id, user_id, user_id, user_id, user_id])
        
        conversations = []
        for row in cursor.fetchall():
            conversations.append({
                'user_id': row[0],
                'name': f"{row[1]} {row[2]}",
                'email': row[3],
                'last_message': row[4],
                'last_message_date': row[5]
            })

    # Get all valid provinces from the schema
    provinces = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]

    # Render dashboard with venues, conversations, and filter options
    return render(request, 'client/c_dashboard.html', {
        'venues': venues,
        'conversations': conversations,
        'search_query': search_query,
        'selected_categories': categories,  # Pass selected categories back to template
        'province': province,
        'city': city,
        'street': street,
        'status': status,
        'rate': rate,
        'availability_type': availability_type,
        'has_venues': len(venues) > 0,
        'provinces': provinces,
        'categories': [
            'Wedding Hall', 'Conference Center', 'Banquet Hall', 'Music Venue', 'Outdoor Park',
            'Rooftop Terrace', 'Studio Space', 'Private Dining Room', 'Theater', 'Exhibition Center',
            'Garden Venue', 'Community Hall', 'Co-working Space',
            'Winter Venue', 'Spring Venue', 'Summer Venue', 'Fall Venue'
        ]
    })

def venue_detail(request, venue_id):
    user_id = request.session.get('user_id')
    
    if not user_id:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('users:login')
        
    try:
        with connection.cursor() as cursor:
            # Select venue details including owner information
            cursor.execute("""
                SELECT v.venue_id, v.name, v.rate, v.status, v.image_url, v.description,
                    v.capacity, v.street, v.city, v.province, v.postal_code,
                    GROUP_CONCAT(DISTINCT vc.category) as categories,
                    vc.availability_type,
                    u.first_name, u.last_name, u.email, u.phone,
                    v.user_id
                FROM venue v
                LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
                LEFT JOIN users u ON v.user_id = u.user_id
                WHERE v.venue_id = %s
                GROUP BY v.venue_id, v.name, v.rate, v.status, v.image_url, v.description,
                         v.capacity, v.street, v.city, v.province, v.postal_code,
                         vc.availability_type, u.first_name, u.last_name, u.email, u.phone,
                         v.user_id
            """, [venue_id])
            
            row = cursor.fetchone()
            
            if not row:
                messages.error(request, "Venue not found.")
                return redirect('users:client_dashboard')
                
            image_url = row[4]
            if image_url and not image_url.startswith('/media/'):
                image_url = f'/media/{image_url}'
                image_url = request.build_absolute_uri(image_url)
                
            # Create venue dictionary with formatted data
            venue = {
                'id': row[0],
                'name': row[1],
                'price': float(row[2]) if row[2] else 0.0,  # Handle decimal(10,2)
                'status': row[3],  # enum('Active','Inactive','Under Maintenance')
                'image_url': image_url,
                'description': row[5],
                'capacity': row[6],
                'street': row[7],
                'city': row[8],
                'province': row[9], 
                'postal_code': row[10],
                'categories': row[11].split(',') if row[11] else [],
                'availability': row[12],  
                'vendor_name': f"{row[13]} {row[14]}",
                'vendor_email': row[15],
                'vendor_phone': row[16],
                'user_id': row[17]
            }
            
            return render(request, 'client/venue_detail.html', {
                'venue': venue
            })
            
    except Exception as e:
        messages.error(request, "Could not load venue details.")
        return redirect('users:client_dashboard')

def venue_booking(request, venue_id):
    # Verify user authentication and retrieve user ID from session
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Please log in to make a booking.")
        return redirect('users:login')

    # Fetch venue details including owner information and categories
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT v.name, v.rate, v.capacity, v.street, v.city, v.province, 
                   v.postal_code, v.image_url, v.description, v.status,
                   u.first_name, u.last_name, u.email, u.phone,
                   GROUP_CONCAT(vc.category) as categories
            FROM venue v
            JOIN users u ON v.user_id = u.user_id
            LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
            WHERE v.venue_id = %s
            GROUP BY v.venue_id
        """, [venue_id])
        venue_data = cursor.fetchone()

    # Verify venue exists and is active
    if not venue_data or venue_data[9] != 'Active':
        messages.error(request, "Venue not available for booking.")
        return redirect('users:client_dashboard')

    # Format venue data for display
    venue = {
        'venue_id': venue_id,
        'name': venue_data[0],
        'rate': float(venue_data[1]),
        'capacity': venue_data[2],
        'street': venue_data[3],
        'city': venue_data[4],
        'province': venue_data[5],
        'postal_code': venue_data[6],
        'image_url': venue_data[7] if venue_data[7] and venue_data[7].startswith('/media/') else f'/media/{venue_data[7]}',
        'description': venue_data[8],
        'vendor_name': f"{venue_data[10]} {venue_data[11]}",
        'vendor_email': venue_data[12],
        'vendor_phone': venue_data[13],
        'categories': venue_data[14].split(',') if venue_data[14] else []
    }

    # Handle POST request for booking submission
    if request.method == 'POST':
        try:
            # Get and validate booking details from form
            start_date = request.POST.get('start_date')
            start_time = request.POST.get('start_time')
            end_date = request.POST.get('end_date')
            end_time = request.POST.get('end_time')
            card_number = request.POST.get('card_number', '').replace(' ', '')  # Remove spaces
            expiry_date = request.POST.get('expiry_date', '').strip()  # YYYY-MM format
            method = request.POST.get('method', '').strip()
            cvv = request.POST.get('cvv', '').strip()

            if not all([start_date, start_time, end_date, end_time, card_number, expiry_date, method, cvv]):
                missing_fields = []
                if not start_date: missing_fields.append('start date')
                if not start_time: missing_fields.append('start time')
                if not end_date: missing_fields.append('end date')
                if not end_time: missing_fields.append('end time')
                if not card_number: missing_fields.append('card number')
                if not expiry_date: missing_fields.append('expiry date')
                if not method: missing_fields.append('payment method')
                if not cvv: missing_fields.append('cvv')
                raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

            # Parse datetime objects for booking period
            try:
                start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
                end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
                
                # Basic validation checks
                current_time = datetime.now()
                
                if start_datetime <= current_time:
                    raise ValueError("Booking start time must be in the future")
                
                if end_datetime <= start_datetime:
                    raise ValueError("End time must be after start time")
                
                # Calculate duration
                duration_hours = (end_datetime - start_datetime).total_seconds() / 3600
                if duration_hours < 1:
                    raise ValueError("Booking must be at least 1 hour long")
                
                total_amount = venue['rate'] * duration_hours

            except ValueError as e:
                raise ValueError(f"Invalid date/time: {str(e)}")

            # Validate card expiry date
            try:
                expiry_year, expiry_month = expiry_date.split('-')
                current_date = datetime.now()
                expiry_date_obj = datetime.strptime(f"{expiry_year}-{expiry_month}-01", "%Y-%m-%d")
                if expiry_date_obj < current_date:
                    raise ValueError("Card has expired")
            except ValueError as e:
                raise ValueError(f"Invalid expiry date: {str(e)}")

            # Use a single connection for all database operations
            with connection.cursor() as cursor:
                # Check for booking overlaps
                cursor.execute("""
                    SELECT COUNT(*) FROM booking
                    WHERE venue_id = %s
                    AND (
                        (start_date < %s AND end_date > %s)
                        OR (start_date < %s AND end_date > %s)
                        OR (start_date >= %s AND start_date < %s)
                        OR (end_date > %s AND end_date <= %s)
                    )
                """, [
                    venue_id,
                    end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    end_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    end_datetime.strftime('%Y-%m-%d %H:%M:%S')
                ])
                if cursor.fetchone()[0] > 0:
                    return render(request, 'client/venue_booking.html', {
                        'venue': venue,
                        'venue_id': venue_id,
                        'form_data': request.POST,
                        'booking_conflict': True
                    })

                # Create payment record
                cursor.execute("""
                    INSERT INTO payment (method, amount, card_last_four, card_expiry, rate)
                    VALUES (%s, %s, %s, %s, %s)
                """, [
                    method,
                    total_amount,
                    card_number[-4:],
                    expiry_date,
                    venue['rate']
                ])
                payment_id = cursor.lastrowid

                # Get client information for notifications
                cursor.execute("""
                    SELECT first_name, last_name, email
                    FROM users
                    WHERE user_id = %s
                """, [user_id])
                client_info = cursor.fetchone()
                client_name = f"{client_info[0]} {client_info[1]}"
                client_email = client_info[2]

                # Create booking record
                cursor.execute("""
                    INSERT INTO booking (user_id, venue_id, payment_id, start_date, end_date)
                    VALUES (%s, %s, %s, %s, %s)
                """, [
                    user_id,
                    venue_id,
                    payment_id,
                    start_datetime.strftime('%Y-%m-%d %H:%M:%S'),
                    end_datetime.strftime('%Y-%m-%d %H:%M:%S')
                ])
                booking_id = cursor.lastrowid

                # Send email notification
                try:
                    send_and_log_notification(
                        cursor,
                        "Booking Confirmation",
                        client_email,
                        client_name,
                        venue['name'],
                        booking_id,
                        venue_id,
                        user_id,
                        payment_id,
                        start_datetime,
                        end_datetime
                    )
                except Exception as e:
                    # Log the notification error but don't fail the booking
                    print(f"Failed to send notification: {str(e)}")

                # Commit all database changes
                connection.commit()

            messages.success(request, "Booking confirmed successfully!")
            return redirect('users:client_dashboard')

        except ValueError as e:
            messages.error(request, str(e))
            return render(request, 'client/venue_booking.html', {
                'venue': venue,
                'venue_id': venue_id,
                'form_data': request.POST
            })
        except Exception as e:
            messages.error(request, f"Failed to process booking: {str(e)}")
            return render(request, 'client/venue_booking.html', {
                'venue': venue,
                'venue_id': venue_id,
                'form_data': request.POST
            })

    # Handle GET request - calculate total amount based on time parameters
    start_date = request.GET.get('start_date')
    start_time = request.GET.get('start_time')
    end_date = request.GET.get('end_date')
    end_time = request.GET.get('end_time')

    if all([start_date, start_time, end_date, end_time]):
        try:
            start_datetime = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
            end_datetime = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")
            duration_hours = (end_datetime - start_datetime).total_seconds() / 3600
            total_amount = venue['rate'] * duration_hours
            venue['total_amount'] = total_amount
        except ValueError:
            messages.error(request, "Invalid date/time format.")

    return render(request, 'client/venue_booking.html', {
        'venue': venue,
        'venue_id': venue_id,
        'booking_conflict': False
    })

def view_bookings(request):
    # Verify user authentication
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Please log in to view your bookings.")
        return redirect('users:login')

    try:
        # Get current datetime for booking status checks
        current_datetime = timezone.now()
        min_cancel_date = current_datetime + timedelta(days=5)
        
        # Get client information for notifications
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT first_name, last_name, email
                FROM users
                WHERE user_id = %s
            """, [user_id])
            client_info = cursor.fetchone()
            client_name = f"{client_info[0]} {client_info[1]}"
            client_email = client_info[2]
        
        # Handle booking cancellation
        if request.method == 'POST' and 'cancel_booking' in request.POST:
            booking_id = request.POST.get('booking_id')
            
            with connection.cursor() as cursor:
                # Verify booking exists and meets cancellation requirements
                cursor.execute("""
                    SELECT b.booking_id, b.start_date, b.venue_id, v.name, b.payment_id, b.user_id 
                    FROM booking b
                    JOIN venue v ON b.venue_id = v.venue_id 
                    WHERE b.booking_id = %s 
                    AND b.user_id = %s
                    AND b.start_date >= %s
                """, [booking_id, user_id, min_cancel_date])
                
                booking = cursor.fetchone()
                
                if booking:
                    # Get booking details for cancellation notification
                    booking_id = booking[0]
                    venue_id = booking[2]
                    venue_name = booking[3]
                    payment_id = booking[4]
                    
                    # Send cancellation notification
                    send_and_log_notification(
                        cursor,
                        "Cancellation",
                        client_email,
                        client_name,
                        venue_name,
                        booking_id,
                        venue_id,
                        user_id,
                        payment_id
                    )

                    # Delete the booking
                    cursor.execute("""
                        DELETE FROM booking 
                        WHERE booking_id = %s
                    """, [booking_id])

                    connection.commit()
                    messages.success(request, "Booking successfully cancelled. A confirmation email has been sent.")
                    return redirect('users:view_bookings')
                else:
                    messages.error(request, "Cannot cancel booking. Either it doesn't exist or it's within 5 days.")
                    return redirect('users:view_bookings')

        # Get current bookings (future or ongoing)
        current_bookings = []
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT b.booking_id, b.start_date, b.end_date, 
                       v.venue_id, v.name, v.image_url,
                       p.amount, p.method, p.card_last_four,
                       CONCAT(u.first_name, ' ', u.last_name) AS vendor_name,
                       b.start_date >= %s as can_cancel
                FROM booking b
                JOIN venue v ON b.venue_id = v.venue_id
                JOIN payment p ON b.payment_id = p.payment_id
                JOIN users u ON v.user_id = u.user_id
                WHERE b.user_id = %s AND b.end_date >= %s
                ORDER BY b.start_date ASC
            """, [min_cancel_date, user_id, current_datetime])
            
            for row in cursor.fetchall():
                # Format image URL for display
                image_url = row[5]
                if image_url and not image_url.startswith('/media/'):
                    image_url = f'/media/{image_url}'
                    image_url = request.build_absolute_uri(image_url)
                
                # Create booking dictionary with formatted data
                current_bookings.append({
                    'id': row[0],
                    'start_date': row[1],
                    'end_date': row[2],
                    'venue_id': row[3],
                    'venue_name': row[4],
                    'venue_image': image_url,
                    'amount': float(row[6]),
                    'payment_method': row[7],
                    'card_last_four': row[8],
                    'vendor_name': row[9],
                    'can_cancel': bool(row[10]),
                    'is_past': False
                })

        # Get past bookings
        past_bookings = []
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT b.booking_id, b.start_date, b.end_date, 
                       v.venue_id, v.name, v.image_url,
                       p.amount, p.method, p.card_last_four,
                       CONCAT(u.first_name, ' ', u.last_name) AS vendor_name
                FROM booking b
                JOIN venue v ON b.venue_id = v.venue_id
                JOIN payment p ON b.payment_id = p.payment_id
                JOIN users u ON v.user_id = u.user_id
                WHERE b.user_id = %s AND b.end_date < %s
                ORDER BY b.end_date DESC
                LIMIT 20
            """, [user_id, current_datetime])
            
            for row in cursor.fetchall():
                # Format image URL for display
                image_url = row[5]
                if image_url and not image_url.startswith('/media/'):
                    image_url = f'/media/{image_url}'
                    image_url = request.build_absolute_uri(image_url)
                
                # Create booking dictionary with formatted data
                past_bookings.append({
                    'id': row[0],
                    'start_date': row[1],
                    'end_date': row[2],
                    'venue_id': row[3],
                    'venue_name': row[4],
                    'venue_image': image_url,
                    'amount': float(row[6]),
                    'payment_method': row[7],
                    'card_last_four': row[8],
                    'vendor_name': row[9],
                    'is_past': True
                })

        return render(request, 'client/view_bookings.html', {
            'current_bookings': current_bookings,
            'past_bookings': past_bookings,
            'has_current': len(current_bookings) > 0,
            'has_past': len(past_bookings) > 0,
            'min_cancel_days': 5
        })

    except Exception as e:
        messages.error(request, "Could not load bookings.")
        return redirect('users:client_dashboard')

def message_vendor(request, vendor_id):
    # Verify user authentication
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, "Please log in to message vendors.")
        return redirect('users:login')

    try:
        with connection.cursor() as cursor:
            # Get vendor details
            cursor.execute("""
                SELECT first_name, last_name, email, user_type
                FROM users
                WHERE user_id = %s AND user_type = 'Vendor'
            """, [vendor_id])
            
            vendor = cursor.fetchone()
            if not vendor:
                messages.error(request, "Vendor not found.")
                return redirect('users:client_dashboard')
                
            vendor_info = {
                'id': vendor_id,
                'name': f"{vendor[0]} {vendor[1]}",
                'email': vendor[2]
            }
            
            # Get conversation history
            cursor.execute("""
                SELECT m.message_id, m.content, m.date_sent,
                       s.first_name as sender_first_name,
                       s.last_name as sender_last_name,
                       m.sender_id
                FROM message m
                JOIN users s ON m.sender_id = s.user_id
                WHERE (m.sender_id = %s AND m.receiver_id = %s)
                   OR (m.sender_id = %s AND m.receiver_id = %s)
                ORDER BY m.date_sent ASC
            """, [user_id, vendor_id, vendor_id, user_id])
            
            messages_list = []
            for row in cursor.fetchall():
                messages_list.append({
                    'id': row[0],
                    'content': row[1],
                    'date_sent': row[2],
                    'sender_name': f"{row[3]} {row[4]}",
                    'is_mine': row[5] == user_id
                })
            
            return render(request, 'client/message_vendor.html', {
                'vendor': vendor_info,
                'messages': messages_list
            })
            
    except Exception as e:
        messages.error(request, "Could not load message interface.")
        return redirect('users:client_dashboard')

def send_message(request):
    # Verify request method and user authentication
    if request.method != 'POST':
        return redirect('users:client_dashboard')
        
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Not logged in'}, status=401)
        
    try:
        # Extract message details
        receiver_id = request.POST.get('receiver_id')
        content = request.POST.get('content')
        
        if not content or not content.strip():
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
            
        with connection.cursor() as cursor:
            # Verify receiver exists and is a vendor
            cursor.execute("""
                SELECT user_id FROM users
                WHERE user_id = %s AND user_type = 'Vendor'
            """, [receiver_id])
            
            if not cursor.fetchone():
                return JsonResponse({'error': 'Invalid receiver'}, status=400)
                
            # Insert the message
            cursor.execute("""
                INSERT INTO message (sender_id, receiver_id, content)
                VALUES (%s, %s, %s)
            """, [user_id, receiver_id, content.strip()])
            
            message_id = cursor.lastrowid
            
            # Get sender name for response
            cursor.execute("""
                SELECT first_name, last_name
                FROM users
                WHERE user_id = %s
            """, [user_id])
            
            sender = cursor.fetchone()
            sender_name = f"{sender[0]} {sender[1]}"
            
            connection.commit()
            
            return JsonResponse({
                'success': True,
                'message': {
                    'id': message_id,
                    'content': content.strip(),
                    'sender_name': sender_name,
                    'date_sent': timezone.now().strftime('%Y-%m-%d %H:%M:%S'),
                    'is_mine': True
                }
            })
            
    except Exception as e:
        return JsonResponse({'error': 'Failed to send message'}, status=500)

def client_messages(request):
    # Verify user authentication
    user_id = request.session.get('user_id')
    if not user_id:
        messages.error(request, 'Please log in to view your messages.')
        return redirect('users:client_login')

    try:
        with connection.cursor() as cursor:
            # Get all conversations with vendors including the last message and date
            cursor.execute("""
                SELECT DISTINCT 
                    v.user_id as vendor_id,
                    CONCAT(v.first_name, ' ', v.last_name) as vendor_name,
                    v.email as vendor_email,
                    COALESCE(
                        (
                            SELECT content 
                            FROM message m2 
                            WHERE (m2.sender_id = v.user_id AND m2.receiver_id = %s)
                               OR (m2.sender_id = %s AND m2.receiver_id = v.user_id)
                            ORDER BY m2.date_sent DESC 
                            LIMIT 1
                        ), 'No messages yet'
                    ) as last_message,
                    COALESCE(
                        (
                            SELECT date_sent 
                            FROM message m3 
                            WHERE (m3.sender_id = v.user_id AND m3.receiver_id = %s)
                               OR (m3.sender_id = %s AND m3.receiver_id = v.user_id)
                            ORDER BY m3.date_sent DESC 
                            LIMIT 1
                        ), NOW()
                    ) as last_message_date
                FROM message m
                JOIN users v ON (m.sender_id = v.user_id OR m.receiver_id = v.user_id)
                WHERE (m.sender_id = %s OR m.receiver_id = %s)
                AND v.user_id != %s
                AND v.user_type = 'Vendor'
                ORDER BY 
                    last_message_date DESC
            """, [user_id, user_id, user_id, user_id, user_id, user_id, user_id])
            
            conversations = []
            for row in cursor.fetchall():
                conversations.append({
                    'vendor_id': row[0],
                    'vendor_name': row[1],
                    'vendor_email': row[2],
                    'last_message': row[3],
                    'last_message_date': row[4]
                })

        return render(request, 'client/messages.html', {
            'conversations': conversations,
            'has_conversations': bool(conversations)
        })

    except Exception as e:
        messages.error(request, 'Failed to load messages. Please try again later.')
        return redirect('users:client_dashboard')