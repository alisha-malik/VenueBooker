from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.utils import timezone
from datetime import datetime, timedelta
import sys
from django.core.mail import send_mail
from django.conf import settings

def send_and_log_notification(cursor, email_type, to_email, user_name, venue_name, booking_id, venue_id, user_id, payment_id=None, start_dt=None, end_dt=None):
    # Compose email based on type
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

    # Log the notification in the database
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

    print("[Reminder Job] Sent reminders for bookings 2 days away.")
        
def client_dashboard(request):
    user_id = request.session.get('user_id')
    print(f"[DEBUG] Starting client_dashboard for user_id: {user_id}", flush=True)

    if not user_id:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('users:login')

    try:
        # Get filter parameters from the request
        filters = {
            'venue_name': request.GET.get('venue_name', ''),
            'province': request.GET.get('province', ''),
            'city': request.GET.get('city', ''),
            'rate': request.GET.get('rate', ''),
            'status': request.GET.get('status', ''),
            'availability_type': request.GET.get('availability_type', ''),
            'selected_categories': request.GET.getlist('categories', []),
        }

        base_query = """
            SELECT v.venue_id, v.name, v.rate, v.status, v.image_url, v.description,
                v.capacity, v.street, v.city, v.province, 
                GROUP_CONCAT(DISTINCT vc.category) as categories, vc.availability_type
            FROM venue v
            LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
            WHERE 1=1
        """
        params = []

        # Only add filters if they are actually set
        if filters['venue_name']:
            base_query += " AND v.name LIKE %s"
            params.append(f"%{filters['venue_name']}%")
        if filters['province']:
            base_query += " AND v.province = %s"
            params.append(filters['province'])
        if filters['city']:
            base_query += " AND v.city LIKE %s"
            params.append(f"%{filters['city']}%")
        if filters['rate']:
            base_query += " AND v.rate <= %s"
            params.append(filters['rate'])
        if filters['status']:
            base_query += " AND v.status = %s"
            params.append(filters['status'])
        if filters['availability_type']:
            base_query += " AND vc.availability_type = %s"
            params.append(filters['availability_type'])
        if filters['selected_categories']:
            placeholders = ', '.join(['%s'] * len(filters['selected_categories']))
            base_query += f" AND vc.category IN ({placeholders})"
            params.extend(filters['selected_categories'])

        base_query += " GROUP BY v.venue_id, vc.availability_type ORDER BY v.name"

        venues = []
        with connection.cursor() as cursor:
            cursor.execute(base_query, params)
            venue_rows = cursor.fetchall()
            print(f"[DEBUG] Number of venues fetched: {len(venue_rows)}", flush=True)

            for row in venue_rows:
                image_url = row[4]
                if image_url:
                    # Ensure the URL starts with /media/
                    if not image_url.startswith('/media/'):
                        image_url = f'/media/{image_url}'
                    
                    # Convert to absolute URL for templates
                    image_url = request.build_absolute_uri(image_url)

                venue = {
                    'id': row[0],
                    'name': row[1],
                    'price': float(row[2]) if row[2] else 0.0,
                    'status': row[3],
                    'image_url': image_url,
                    'description': row[5],
                    'capacity': row[6],
                    'street': row[7],
                    'city': row[8],
                    'province': row[9],
                    'categories': row[10].split(',') if row[10] else [],
                    'availability': row[11] or 'Full-Year'
                }
                venues.append(venue)

        has_venues = len(venues) > 0

        # Get all categories for filter options
        categories = []
        seasons = ['Spring', 'Summer', 'Fall', 'Winter']
        provinces = ['AB','BC','MB','NB','NL','NS','NT','NU','ON','PE','QC','SK','YT']
        
        with connection.cursor() as cursor:
            cursor.execute("SELECT DISTINCT category FROM venue_category WHERE category NOT IN ('Spring', 'Summer', 'Fall', 'Winter')")
            for row in cursor.fetchall():
                categories.append(row[0])

        return render(request, 'client/c_dashboard.html', {
            'venues': venues,
            'has_venues': has_venues,
            'categories': categories,
            'seasons': seasons,
            'provinces': provinces,
            'field_values': filters,  # Pass the filter values back to the template
            'field_errors': {}  # Empty dictionary for any validation errors
        })

    except Exception as e:
        print(f"[DEBUG] client_dashboard error → {e}", flush=True)
        messages.error(request, "Could not load dashboard.")
        return redirect('users:login')

def venue_detail(request, venue_id):
    user_id = request.session.get('user_id')
    
    if not user_id:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('users:login')
        
    try:
        with connection.cursor() as cursor:
            # Updated the table name from 'user' to 'users'
            cursor.execute("""
                SELECT v.venue_id, v.name, v.rate, v.status, v.image_url, v.description,
                    v.capacity, v.street, v.city, v.province, v.postal_code,
                    GROUP_CONCAT(DISTINCT vc.category) as categories,
                    vc.availability_type,
                    u.first_name, u.last_name, u.email, u.phone
                FROM venue v
                LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
                LEFT JOIN users u ON v.user_id = u.user_id
                WHERE v.venue_id = %s
                GROUP BY v.venue_id, vc.availability_type
            """, [venue_id])
            
            row = cursor.fetchone()
            
            if not row:
                messages.error(request, "Venue not found.")
                return redirect('users:client_dashboard')
                
            image_url = row[4]
            if image_url and not image_url.startswith('/media/'):
                image_url = f'/media/{image_url}'
                image_url = request.build_absolute_uri(image_url)
                
            venue = {
                'id': row[0],
                'name': row[1],
                'price': float(row[2]) if row[2] else 0.0,
                'status': row[3],
                'image_url': image_url,
                'description': row[5],
                'capacity': row[6],
                'street': row[7],
                'city': row[8],
                'province': row[9],
                'postal_code': row[10],
                'categories': row[11].split(',') if row[11] else [],
                'availability': row[12] or 'Full-Year',
                'vendor_name': f"{row[13]} {row[14]}",
                'vendor_email': row[15],
                'vendor_phone': row[16]
            }
            
            return render(request, 'client/venue_detail.html', {
                'venue': venue
            })
            
    except Exception as e:
        print(f"[DEBUG] venue_detail error → {e}", flush=True)
        messages.error(request, "Could not load venue details.")
        return redirect('users:client_dashboard')

def venue_booking(request, venue_id):
    user_id = request.session.get('user_id')
    print(f"[DEBUG] Starting venue_booking for venue_id: {venue_id}, user_id: {user_id}", flush=True)

    if not user_id:
        messages.error(request, "You must be logged in to book a venue.")
        return redirect('users:login')

    if request.session.get('user_type') != 'Client':
        messages.error(request, "Only clients can book venues.")
        return redirect('users:client_dashboard')

    try:
        with connection.cursor() as cursor:
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
                GROUP BY v.venue_id, vc.availability_type
            """, [venue_id])

            row = cursor.fetchone()

            if not row:
                messages.error(request, "Venue not found.")
                return redirect('users:client_dashboard')

            # Get client information for email notifications
            cursor.execute("""
                SELECT first_name, last_name, email
                FROM users
                WHERE user_id = %s
            """, [user_id])
            client_info = cursor.fetchone()
            client_name = f"{client_info[0]} {client_info[1]}"
            client_email = client_info[2]

            if request.method == 'POST':
                try:
                    start_date = request.POST.get('start_date')
                    end_date = request.POST.get('end_date')
                    start_time = request.POST.get('start_time')
                    end_time = request.POST.get('end_time')
                    method = request.POST.get('method')
                    card_number = ''.join(filter(str.isdigit, request.POST.get('card_number', '')))
                    expiry_date = request.POST.get('expiry_date')

                    from datetime import datetime, timedelta
                    start_dt = datetime.strptime(f"{start_date} {start_time}", "%Y-%m-%d %H:%M")
                    end_dt = datetime.strptime(f"{end_date} {end_time}", "%Y-%m-%d %H:%M")

                    duration = (end_dt - start_dt).total_seconds() / 3600
                    hourly_rate = float(row[2])
                    total_amount = round(duration * hourly_rate, 2)

                    if total_amount <= 0:
                        messages.error(request, "Invalid booking duration. Please ensure your end time is after your start time.")
                        raise ValueError("Invalid booking duration")

                    if expiry_date:
                        try:
                            expiry_year, expiry_month = map(int, expiry_date.split('-'))
                            current_date = datetime.now()
                            if expiry_year < current_date.year or (expiry_year == current_date.year and expiry_month < current_date.month):
                                messages.error(request, "Card has expired.")
                                raise ValueError("Expired card")
                        except ValueError:
                            messages.error(request, "Invalid expiry date format.")
                            raise ValueError("Invalid expiry")
                    else:
                        messages.error(request, "Missing expiry date.")
                        raise ValueError("Missing expiry")

                    with connection.cursor() as cursor:
                        print(f"[DEBUG] Starting transaction for payment and booking", flush=True)

                        cursor.execute("""
                            SELECT COUNT(*) FROM booking
                            WHERE venue_id = %s AND (
                                (%s < end_date AND %s > start_date)
                            )
                        """, [venue_id, start_dt, end_dt])
                        (overlap_count,) = cursor.fetchone()

                        if overlap_count > 0:
                            messages.error(request, "This venue is already booked during the selected time period.")
                            raise ValueError("Venue already booked")

                        card_last_four = card_number[-4:] if len(card_number) >= 4 else ''

                        cursor.execute("""
                            INSERT INTO payment (
                                method, rate, amount, card_last_four, card_expiry
                            ) VALUES (%s, %s, %s, %s, %s)
                        """, [method, hourly_rate, total_amount, card_last_four, expiry_date])

                        payment_id = cursor.lastrowid
                        print(f"[DEBUG] Payment record created with ID: {payment_id}", flush=True)

                        cursor.execute("""
                            INSERT INTO booking (
                                venue_id, user_id, start_date, end_date, payment_id
                            ) VALUES (%s, %s, %s, %s, %s)
                        """, [venue_id, user_id, start_dt, end_dt, payment_id])
                        
                        booking_id = cursor.lastrowid
                        print(f"[DEBUG] Booking record created with ID: {booking_id}", flush=True)
                        
                        # Send booking confirmation email
                        venue_name = row[1]
                        vendor_id = row[17]
                        
                        send_and_log_notification(
                            cursor, 
                            "Booking Confirmation", 
                            client_email,
                            client_name,
                            venue_name,
                            booking_id,
                            venue_id,
                            user_id,
                            payment_id,
                            start_dt,
                            end_dt
                        )

                    connection.commit()
                    messages.success(request, "Venue booked successfully! A confirmation email has been sent.")
                    return redirect('users:client_dashboard')

                except ValueError as e:
                    print(f"[DEBUG] Validation error: {e}", flush=True)
                    if not messages.get_messages(request):
                        messages.error(request, str(e))
                except Exception as e:
                    print(f"[DEBUG] Booking error: {e}", flush=True)
                    messages.error(request, "An error occurred while processing your booking.")
                    connection.rollback()

            total_amount = None
            if request.method == 'GET' and 'start_time' in request.GET and 'end_time' in request.GET:
                try:
                    start_time = request.GET['start_time']
                    end_time = request.GET['end_time']
                    start_dt = datetime.strptime(f"2000-01-01 {start_time}", "%Y-%m-%d %H:%M")
                    end_dt = datetime.strptime(f"2000-01-01 {end_time}", "%Y-%m-%d %H:%M")
                    if end_dt < start_dt:
                        end_dt += timedelta(days=1)
                    duration = (end_dt - start_dt).total_seconds() / 3600
                    total_amount = round(duration * float(row[2]), 2)
                except:
                    total_amount = None

            image_url = row[4]
            if image_url and not image_url.startswith('/media/'):
                image_url = f'/media/{image_url}'
                image_url = request.build_absolute_uri(image_url)

            venue = {
                'venue_id': row[0], 'name': row[1], 'price': float(row[2]) if row[2] else 0.0,
                'status': row[3], 'image_url': image_url, 'description': row[5],
                'capacity': row[6], 'street': row[7], 'city': row[8], 'province': row[9],
                'postal_code': row[10], 'categories': row[11].split(',') if row[11] else [],
                'availability': row[12] or 'Full-Year',
                'vendor_name': f"{row[13]} {row[14]}", 'vendor_email': row[15], 'vendor_phone': row[16]
            }

            context = {'venue': venue, 'total_amount': total_amount}
            return render(request, 'client/venue_booking.html', context)

    except Exception as e:
        print(f"[DEBUG] venue_booking error → {e}", flush=True)
        return redirect('users:client_dashboard')

def view_bookings(request):
    user_id = request.session.get('user_id')
    print(f"[DEBUG] Starting view_bookings for user_id: {user_id}", flush=True)

    if not user_id:
        messages.error(request, "You must be logged in to view bookings.")
        return redirect('users:login')

    try:
        current_datetime = timezone.now()
        min_cancel_date = current_datetime + timedelta(days=5)
        
        # Get client information for email notifications
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
                # Check if booking exists and meets cancellation criteria
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
                    # Get booking details for cancellation email
                    booking_id = booking[0]
                    venue_id = booking[2]
                    venue_name = booking[3]
                    payment_id = booking[4]
                    
                    # Format the cancellation email before deleting from the database
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
                image_url = row[5]
                if image_url and not image_url.startswith('/media/'):
                    image_url = f'/media/{image_url}'
                    image_url = request.build_absolute_uri(image_url)
                
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
                image_url = row[5]
                if image_url and not image_url.startswith('/media/'):
                    image_url = f'/media/{image_url}'
                    image_url = request.build_absolute_uri(image_url)
                
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
        print(f"[DEBUG] view_bookings error → {e}", file=sys.stderr)
        messages.error(request, "Could not load bookings.")
        return redirect('users:client_dashboard')