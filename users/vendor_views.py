"""
Vendor Views Module

This module contains all the view functions for vendors in the VenueBooker system.
It handles venue management, booking tracking, and communication with clients.

Key Functionalities:
1. Venue Management
2. Booking Management
3. Communication
4. Profile Management
5. Analytics
"""

import os
import re
import time

from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.conf import settings
from django.http import JsonResponse
from django.utils import timezone

def vendor_dashboard(request):
    # Get user_id from session to verify authentication
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('users:login')

    try:
        venues = []

        with connection.cursor() as cursor:
            # Query to get all venues owned by the current vendor
            # Includes venue details and categories through LEFT JOIN
            cursor.execute("""
                SELECT v.venue_id, v.name, v.rate, v.status, v.image_url, v.description, 
                       v.capacity, GROUP_CONCAT(vc.category), vc.availability_type, v.city
                FROM venue v
                LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
                WHERE v.user_id = %s
                GROUP BY v.venue_id, vc.availability_type
                ORDER BY v.name
            """, [user_id])

            venue_rows = cursor.fetchall()

            # Process each venue row and format the data
            for row in venue_rows:
                # Handle image URL formatting
                image_url = row[4]
                if image_url:
                    # Ensure the URL starts with /media/ for proper serving
                    if not image_url.startswith('/media/'):
                        image_url = f'/media/{image_url}'
                    
                    # Convert to absolute URL for templates
                    image_url = request.build_absolute_uri(image_url)

                # Create venue dictionary with formatted data
                venue = {
                    'id': row[0],
                    'name': row[1],
                    'price': float(row[2]) if row[2] else 0.0,
                    'status': row[3],
                    'image_url': image_url,
                    'description': row[5],
                    'capacity': row[6],
                    'categories': row[7].split(',') if row[7] else [],
                    'availability': row[8] or 'Full-Year',
                    'location': row[9]  # Add city as location
                }
                venues.append(venue)

        # Check if vendor has any venues to display
        has_venues = len(venues) > 0

        # Render the dashboard template with venue data
        return render(request, 'vendor/v_dashboard.html', {
            'venues': venues,
            'has_venues': has_venues
        })

    except Exception as e:
        messages.error(request, "Could not load dashboard.")
        return redirect('users:login')

def create_posting(request):
    # Get user_id from session to verify authentication
    user_id = request.session.get('user_id')
    
    # Define available options for venue creation
    provinces = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]
    categories = [
        'Wedding Hall', 'Conference Center', 'Banquet Hall', 'Music Venue',
        'Outdoor Park', 'Rooftop Terrace', 'Studio Space', 'Private Dining Room',
        'Theater', 'Exhibition Center', 'Garden Venue', 'Community Hall', 'Co-working Space'
    ]
    seasons = ['Winter Venue', 'Spring Venue', 'Summer Venue', 'Fall Venue']

    # Initialize error and value storage
    field_errors = {}
    field_values = {}

    if request.method == 'POST':
        # Extract and clean form data
        name = request.POST.get('name', '').strip()
        description = request.POST.get('description', '').strip()
        capacity = request.POST.get('capacity', '').strip()
        availability_type = request.POST.get('availability_type', 'Full-Year')
        selected_categories = request.POST.getlist('categories')
        image = request.FILES.get('image')
        status = request.POST.get('status', 'Active')
        rate = request.POST.get('rate', '').strip()
        street = request.POST.get('street', '').strip()
        city = request.POST.get('city', '').strip()
        province = request.POST.get('province', '').strip()
        postal_code = request.POST.get('postal_code', '').strip().upper()

        # Format postal code if valid but missing a space
        if re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', postal_code):
            postal_code = f"{postal_code[:3]} {postal_code[3:]}"

        # Store form values for potential re-rendering
        field_values.update({
            'name': name,
            'description': description,
            'capacity': capacity,
            'availability_type': availability_type,
            'selected_categories': selected_categories,
            'status': status,
            'rate': rate,
            'street': street,
            'city': city,
            'province': province,
            'postal_code': postal_code,
        })

        # Validate required fields and data formats
        if not name:
            field_errors['name'] = "Venue name is required."
        if not description:
            field_errors['description'] = "Description is required."
        if not capacity.isdigit():
            field_errors['capacity'] = "Enter a valid number for capacity."
        if not rate.replace('.', '', 1).isdigit():
            field_errors['rate'] = "Enter a valid number for rate."
        if not street:
            field_errors['street'] = "Street is required."
        if not city:
            field_errors['city'] = "City is required."
        if not province:
            field_errors['province'] = "Province is required."
        if not postal_code:
            field_errors['postal_code'] = "Postal Code is required."
        elif not re.match(r'^[A-Z]\d[A-Z] \d[A-Z]\d$', postal_code):
            field_errors['postal_code'] = "Postal Code must follow the format A1A 1A1."
        if not image:
            field_errors['image'] = "Venue image is required."

        # Return to form if there are validation errors
        if field_errors:
            return render(request, 'vendor/posting.html', {
                'field_errors': field_errors,
                'field_values': field_values,
                'categories': categories,
                'seasons': seasons,
                'provinces': provinces
            })

        # Check for duplicate venue entries
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM venue
                WHERE user_id = %s AND name = %s AND street = %s AND city = %s AND province = %s AND postal_code = %s
            """, [user_id, name, street, city, province, postal_code])
            duplicate_count = cursor.fetchone()[0]

        # Prevent duplicate venue creation
        if duplicate_count > 0:
            field_errors['name'] = "This venue already exists. Please edit the existing posting instead of creating a new one."
            return render(request, 'vendor/posting.html', {
                'field_errors': field_errors,
                'field_values': field_values,
                'categories': categories,
                'seasons': seasons,
                'provinces': provinces
            })
        
        try:
            # Create media directory if it doesn't exist
            os.makedirs('media', exist_ok=True)
            
            # Generate a unique filename for the image
            original_name = image.name.replace(' ', '_') 
            timestamp = str(int(time.time()))
            filename = f"venue_{timestamp}_{original_name}"
            
            # Save the uploaded image file
            with open(f'media/{filename}', 'wb+') as destination:
                for chunk in image.chunks():
                    destination.write(chunk)
            
            # Store the relative path for database storage
            image_url = f'/media/{filename}'
            
        except Exception as e:
            field_errors['image'] = "Failed to upload image. Please try again."

        # Insert venue details into the database
        with connection.cursor() as cursor:
            # Insert main venue information
            cursor.execute("""
                INSERT INTO venue (name, image_url, description, capacity, status, rate, street, city, province, postal_code, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [name, image_url, description, int(capacity), status, float(rate), street, city, province, postal_code, user_id])
            venue_id = cursor.lastrowid

            # Insert venue categories
            for category in selected_categories:
                cursor.execute("""
                    INSERT INTO venue_category (venue_id, category, availability_type)
                    VALUES (%s, %s, %s)
                """, [venue_id, category, availability_type])

        messages.success(request, "Venue created successfully.")
        return redirect('users:vendor_dashboard')

    # Render the initial venue creation form
    return render(request, 'vendor/posting.html', {
        'categories': categories,
        'seasons': seasons,
        'provinces': provinces
    })

def edit_venue(request, venue_id):
    # Get user_id from session to verify authentication
    user_id = request.session.get('user_id')

    # Retrieve venue details from the database
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, status, rate, street, city, province, postal_code, user_id, image_url, description
            FROM venue
            WHERE venue_id = %s
        """, [venue_id])
        row = cursor.fetchone()

    # Check if venue exists
    if not row:
        messages.error(request, "Venue not found.")
        return redirect('users:vendor_dashboard')

    # Verify venue ownership
    if row[7] != user_id:
        messages.error(request, "Unauthorized access.")
        return redirect('users:vendor_dashboard')

    # Check for active bookings that would prevent editing
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM booking WHERE venue_id = %s", [venue_id])
        has_bookings = cursor.fetchone()[0] > 0

    # Retrieve current venue categories
    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT category, availability_type
            FROM venue_category
            WHERE venue_id = %s
        """, [venue_id])
        categories_data = cursor.fetchall()

    # Extract current categories and availability type
    current_categories = [row[0] for row in categories_data]
    availability_type = categories_data[0][1] if categories_data else "Full-Year"

    # Define available options for editing
    provinces = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]
    all_categories = [
        'Wedding Hall', 'Conference Center', 'Banquet Hall', 'Music Venue', 'Outdoor Park',
        'Rooftop Terrace', 'Studio Space', 'Private Dining Room', 'Theater', 'Exhibition Center',
        'Garden Venue', 'Community Hall', 'Co-working Space'
    ]
    seasons = ['Winter Venue', 'Spring Venue', 'Summer Venue', 'Fall Venue']
    availability_options = ['Full-Year', 'Seasonal']

    # Handle POST request for venue updates
    if request.method == 'POST':
        # Prevent editing if venue has active bookings
        if has_bookings:
            messages.error(request, "Cannot edit this venue. It has active bookings.")
            return redirect('users:vendor_dashboard')

        # Extract and clean form data
        name = request.POST.get('name', '').strip()
        status = request.POST.get('status', 'Active')
        rate = request.POST.get('rate', '').strip()
        street = request.POST.get('street', '').strip()
        city = request.POST.get('city', '').strip()
        province = request.POST.get('province', '').strip()
        postal_code = request.POST.get('postal_code', '').strip().upper()
        selected_categories = request.POST.getlist('categories')
        availability = request.POST.get('availability_type', 'Full-Year')
        description = request.POST.get('description', '').strip()

        # Get current image information
        image = request.FILES.get('image')
        current_image_url = row[8]

        # Format postal code if valid but missing a space
        if re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', postal_code):
            postal_code = f"{postal_code[:3]} {postal_code[3:]}"

        # Validate form data
        field_errors = {}
        if not name:
            field_errors['name'] = "Venue name is required."
        if not description:
            field_errors['description'] = "Description is required."
        if not rate.replace('.', '', 1).isdigit():
            field_errors['rate'] = "Enter a valid number for rate."
        if not street:
            field_errors['street'] = "Street is required."
        if not city:
            field_errors['city'] = "City is required."
        if not province:
            field_errors['province'] = "Province is required."
        if not postal_code:
            field_errors['postal_code'] = "Postal Code is required."
        elif not re.match(r'^[A-Z]\d[A-Z] \d[A-Z]\d$', postal_code):
            field_errors['postal_code'] = "Postal Code must follow the format A1A 1A1."

        # Return to form if there are validation errors
        if field_errors:
            venue = {
                'venue_id': venue_id,
                'name': name,
                'status': status,
                'rate': rate,
                'street': street,
                'city': city,
                'province': province,
                'postal_code': postal_code,
                'has_bookings': has_bookings,
                'selected_categories': selected_categories,
                'availability_type': availability,
                'image_url': current_image_url,
                'description': description
            }
            return render(request, 'vendor/edit_posting.html', {
                'venue': venue,
                'provinces': provinces,
                'all_categories': all_categories,
                'availability_options': availability_options,
                'seasons': seasons,
                'field_errors': field_errors
            })

        try:
            # Handle image upload if a new image is provided
            image_url = current_image_url  # Default to current image
            
            if image:  # If new image was uploaded
                # Create media directory if it doesn't exist
                os.makedirs('media', exist_ok=True)
                
                # Generate a unique filename
                original_name = image.name.replace(' ', '_')
                timestamp = str(int(time.time()))
                filename = f"venue_{timestamp}_{original_name}"
                
                # Save the new image file
                with open(f'media/{filename}', 'wb+') as destination:
                    for chunk in image.chunks():
                        destination.write(chunk)
                
                # Store the new image path
                image_url = f'/media/{filename}'

            # Update venue details in the database
            with connection.cursor() as cursor:
                # Update main venue information
                cursor.execute("""
                    UPDATE venue
                    SET name=%s, status=%s, rate=%s, street=%s, city=%s,
                        province=%s, postal_code=%s, image_url=%s, description=%s
                    WHERE venue_id = %s
                """, [name, status, float(rate), street, city, province, postal_code, image_url, description, venue_id])

                # Delete existing venue categories
                cursor.execute("DELETE FROM venue_category WHERE venue_id = %s", [venue_id])
                
                # Insert new venue categories
                for category in selected_categories:
                    cursor.execute("""
                        INSERT INTO venue_category (venue_id, category, availability_type)
                        VALUES (%s, %s, %s)
                    """, [venue_id, category, availability])

            messages.success(request, "Venue updated successfully.")
            return redirect('users:vendor_dashboard')

        except Exception as e:
            messages.error(request, "Failed to update venue.")

    # Prepare venue data for the edit form
    venue = {
        'venue_id': venue_id,
        'name': row[0],
        'status': row[1],
        'rate': row[2],
        'street': row[3],
        'city': row[4],
        'province': row[5],
        'postal_code': row[6],
        'has_bookings': has_bookings,
        'selected_categories': current_categories,
        'availability_type': availability_type,
        'image_url': row[8],
        'description': row[9]
    }

    # Render the edit form with current venue data
    return render(request, 'vendor/edit_posting.html', {
        'venue': venue,
        'provinces': provinces,
        'all_categories': all_categories,
        'availability_options': availability_options,
        'seasons': seasons,
        'field_errors': field_errors if 'field_errors' in locals() else {}
    })


def delete_venue(request, venue_id):
    # Get user_id from session to verify authentication
    user_id = request.session.get('user_id')

    # Check if the venue exists and belongs to the current vendor
    with connection.cursor() as cursor:
        cursor.execute("SELECT user_id, image_url FROM venue WHERE venue_id = %s", [venue_id])
        row = cursor.fetchone()

    if not row or row[0] != user_id:
        messages.error(request, "Unauthorized access or venue not found.")
        return redirect('users:vendor_dashboard')

    # Check if the venue has any existing bookings
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM booking WHERE venue_id = %s", [venue_id])
        has_bookings = cursor.fetchone()[0] > 0

    if has_bookings:
        messages.error(request, "Cannot delete venue with existing bookings.")
        return redirect('users:vendor_dashboard')

    try:
        # Delete the venue's image file if it exists
        if row[1]:  # If there's an image URL
            image_path = os.path.join(settings.MEDIA_ROOT, row[1].split('/media/')[-1])
            if os.path.exists(image_path):
                os.remove(image_path)

        # Delete the venue record from the database
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM venue WHERE venue_id = %s", [venue_id])

        messages.success(request, "Venue deleted successfully.")
    except Exception as e:
        messages.error(request, "Error deleting venue.")

    return redirect('users:vendor_dashboard')

def vendor_booking_history(request):
    # Get user_id from session to verify authentication
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('users:login')

    # Initialize context with empty venue bookings list
    context = {"venue_bookings": []}

    try:
        with connection.cursor() as cursor:
            # Query to get all venues owned by the current vendor that have bookings
            # Includes basic venue information for display
            cursor.execute("""
                SELECT DISTINCT v.venue_id, v.name, v.image_url, v.city
                FROM venue v
                JOIN booking b ON v.venue_id = b.venue_id
                WHERE v.user_id = %s
                ORDER BY v.name
            """, [user_id])
            venues = cursor.fetchall()

            # Process each venue and its bookings
            for venue_id, venue_name, venue_image, venue_city in venues:
                # Query to get all bookings for the current venue
                # Includes client information and payment details
                cursor.execute("""
                    SELECT CONCAT(u.first_name, ' ', u.last_name) AS client_name,
                           b.start_date, b.end_date, 
                           p.method AS payment_method, 
                           p.card_last_four,
                           b.booking_id
                    FROM booking b
                    JOIN users u ON b.user_id = u.user_id
                    JOIN payment p ON b.payment_id = p.payment_id
                    WHERE b.venue_id = %s
                    ORDER BY b.start_date DESC
                """, [venue_id])
                bookings = cursor.fetchall()

                # Process each booking and format the data
                venue_bookings = []
                for row in bookings:
                    booking_data = {
                        "user_name": row[0],
                        "start_date": row[1],
                        "end_date": row[2],
                        "payment_method": row[3],
                        "card_last_four": row[4],
                        "booking_id": row[5]
                    }
                    venue_bookings.append(booking_data)

                # Format venue image URL for display
                if venue_image:
                    if not venue_image.startswith('/media/'):
                        venue_image = f'/media/{venue_image}'
                    venue_image_url = request.build_absolute_uri(venue_image)
                else:
                    venue_image_url = None

                # Add venue and its bookings to the context
                context["venue_bookings"].append({
                    "venue_id": venue_id,
                    "venue_name": venue_name,
                    "venue_image": venue_image_url,
                    "city": venue_city,
                    "bookings": venue_bookings
                })

    except Exception as e:
        messages.error(request, "Could not load booking history.")
        return redirect('users:vendor_dashboard')

    # Render the booking history template with the prepared data
    return render(request, 'vendor/booking_history.html', context)

def vendor_messages(request):
    user_id = request.session.get('user_id')
    
    if not user_id:
        messages.error(request, "You must be logged in to view messages.")
        return redirect('users:login')

    try:
        with connection.cursor() as cursor:
            # Get all conversations with clients
            cursor.execute("""
                SELECT DISTINCT 
                    u.user_id as client_id,
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
                WHERE u.user_type = 'Client'
                GROUP BY u.user_id
                ORDER BY last_message_date DESC
            """, [user_id, user_id, user_id, user_id, user_id, user_id])
            
            # Process each conversation and format the data
            conversations = []
            for row in cursor.fetchall():
                conversations.append({
                    'client_id': row[0],
                    'client_name': f"{row[1]} {row[2]}",
                    'client_email': row[3],
                    'last_message': row[4],
                    'last_message_date': row[5]
                })

            # Clear any existing messages
            storage = messages.get_messages(request)
            for _ in storage:
                pass

            # Prepare context for the messages template
            return render(request, 'vendor/messages.html', {
                'conversations': conversations,
                'has_conversations': len(conversations) > 0
            })
            
    except Exception as e:
        print(f"[DEBUG] vendor_messages error → {e}", flush=True)
        messages.error(request, "Could not load messages.")
        return redirect('users:vendor_dashboard')

def vendor_chat(request, client_id):
    user_id = request.session.get('user_id')
    
    if not user_id:
        messages.error(request, "You must be logged in to view messages.")
        return redirect('users:login')

    try:
        with connection.cursor() as cursor:
            # Get client details
            cursor.execute("""
                SELECT first_name, last_name, email
                FROM users
                WHERE user_id = %s AND user_type = 'Client'
            """, [client_id])
            client = cursor.fetchone()
            
            if not client:
                messages.error(request, "Client not found.")
                return redirect('users:vendor_messages')
            
            # Get all messages between vendor and client
            cursor.execute("""
                SELECT 
                    m.content,
                    m.date_sent,
                    m.sender_id,
                    CASE 
                        WHEN m.sender_id = %s THEN 'sent'
                        ELSE 'received'
                    END as message_type
                FROM message m
                WHERE (m.sender_id = %s AND m.receiver_id = %s)
                   OR (m.sender_id = %s AND m.receiver_id = %s)
                ORDER BY m.date_sent ASC
            """, [user_id, user_id, client_id, client_id, user_id])
            
            messages_list = []
            for row in cursor.fetchall():
                messages_list.append({
                    'content': row[0],
                    'date_sent': row[1],
                    'sender_id': row[2],
                    'type': row[3]
                })

            # Prepare context for the chat template
            context = {
                'client_name': f"{client[0]} {client[1]}",
                'client_email': client[2],
                'messages': messages_list,
                'client_id': client_id
            }
            
            return render(request, 'vendor/chat.html', context)
            
    except Exception as e:
        print(f"[DEBUG] vendor_chat error → {e}", flush=True)
        messages.error(request, "Could not load chat messages.")
        return redirect('users:vendor_messages')

def send_message(request):
    if request.method != 'POST':
        return redirect('users:vendor_dashboard')
        
    user_id = request.session.get('user_id')
    if not user_id:
        return JsonResponse({'error': 'Not logged in'}, status=401)
        
    try:
        receiver_id = request.POST.get('receiver_id')
        content = request.POST.get('content')
        
        if not content or not content.strip():
            return JsonResponse({'error': 'Message cannot be empty'}, status=400)
            
        with connection.cursor() as cursor:
            # Verify receiver exists and is a client
            cursor.execute("""
                SELECT user_id FROM users
                WHERE user_id = %s AND user_type = 'Client'
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
        print(f"[DEBUG] send_message error → {e}", flush=True)
        return JsonResponse({'error': 'Failed to send message'}, status=500)