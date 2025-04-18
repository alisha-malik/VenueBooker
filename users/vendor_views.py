import os
import re
import time

from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.core.files.storage import FileSystemStorage
from django.conf import settings

def vendor_dashboard(request):
    user_id = request.session.get('user_id')
    print(f"[DEBUG] Starting vendor_dashboard for user_id: {user_id}", flush=True)

    if not user_id:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('users:login')

    try:
        venues = []

        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT v.venue_id, v.name, v.rate, v.status, v.image_url, v.description, 
                       v.capacity, GROUP_CONCAT(vc.category), vc.availability_type
                FROM venue v
                LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
                WHERE v.user_id = %s
                GROUP BY v.venue_id, vc.availability_type
                ORDER BY v.name
            """, [user_id])

            venue_rows = cursor.fetchall()

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
                    'categories': row[7].split(',') if row[7] else [],
                    'availability': row[8] or 'Full-Year'
                }
                venues.append(venue)

        has_venues = len(venues) > 0

        return render(request, 'vendor/v_dashboard.html', {
            'venues': venues,
            'has_venues': has_venues
        })

    except Exception as e:
        print(f"[DEBUG] vendor_dashboard error → {e}", flush=True)
        messages.error(request, "Could not load dashboard.")
        return redirect('users:login')

def create_posting(request):
    user_id = request.session.get('user_id')
    provinces = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]
    categories = [
        'Wedding Hall', 'Conference Center', 'Banquet Hall', 'Music Venue',
        'Outdoor Park', 'Rooftop Terrace', 'Studio Space', 'Private Dining Room',
        'Theater', 'Exhibition Center', 'Garden Venue', 'Community Hall', 'Co-working Space'
    ]
    seasons = ['Winter Venue', 'Spring Venue', 'Summer Venue', 'Fall Venue']

    field_errors = {}
    field_values = {}

    if request.method == 'POST':
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

        # Attempt to auto-format postal code if valid but missing a space
        if re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', postal_code):
            postal_code = f"{postal_code[:3]} {postal_code[3:]}"

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

        # Validation checks
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

        if field_errors:
            return render(request, 'vendor/posting.html', {
                'field_errors': field_errors,
                'field_values': field_values,
                'categories': categories,
                'seasons': seasons,
                'provinces': provinces
            })

        # Check for duplicate venue for this vendor
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT COUNT(*) FROM venue
                WHERE user_id = %s AND name = %s AND street = %s AND city = %s AND province = %s AND postal_code = %s
            """, [user_id, name, street, city, province, postal_code])
            duplicate_count = cursor.fetchone()[0]

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
            
            # Generate a safe filename
            original_name = image.name.replace(' ', '_')  # Replace spaces with underscores
            timestamp = str(int(time.time()))
            filename = f"venue_{timestamp}_{original_name}"
            
            # Save file to media directory
            with open(f'media/{filename}', 'wb+') as destination:
                for chunk in image.chunks():
                    destination.write(chunk)
            
            # Store relative path in database
            image_url = f'/media/{filename}'
            
        except Exception as e:
            print(f"[DEBUG] Failed to save image: {e}")
            field_errors['image'] = "Failed to upload image. Please try again."


        with connection.cursor() as cursor:
            cursor.execute("""
                INSERT INTO venue (name, image_url, description, capacity, status, rate, street, city, province, postal_code, user_id)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            """, [name, image_url, description, int(capacity), status, float(rate), street, city, province, postal_code, user_id])
            venue_id = cursor.lastrowid

            for category in selected_categories:
                cursor.execute("""
                    INSERT INTO venue_category (venue_id, category, availability_type)
                    VALUES (%s, %s, %s)
                """, [venue_id, category, availability_type])

        messages.success(request, "Venue created successfully.")
        return redirect('users:vendor_dashboard')

    return render(request, 'vendor/posting.html', {
        'categories': categories,
        'seasons': seasons,
        'provinces': provinces
    })

def edit_venue(request, venue_id):
    user_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("""
            SELECT name, status, rate, street, city, province, postal_code, user_id, image_url
            FROM venue
            WHERE venue_id = %s
        """, [venue_id])
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Venue not found.")
        return redirect('users:vendor_dashboard')

    if row[7] != user_id:
        messages.error(request, "Unauthorized access.")
        return redirect('users:vendor_dashboard')

    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM booking WHERE venue_id = %s", [venue_id])
        has_bookings = cursor.fetchone()[0] > 0

        cursor.execute("""
            SELECT category, availability_type
            FROM venue_category
            WHERE venue_id = %s
        """, [venue_id])
        categories_data = cursor.fetchall()

    current_categories = [row[0] for row in categories_data]
    availability_type = categories_data[0][1] if categories_data else "Full-Year"

    provinces = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]
    all_categories = [
        'Wedding Hall', 'Conference Center', 'Banquet Hall', 'Music Venue', 'Outdoor Park',
        'Rooftop Terrace', 'Studio Space', 'Private Dining Room', 'Theater', 'Exhibition Center',
        'Garden Venue', 'Community Hall', 'Co-working Space',
        'Winter Venue', 'Spring Venue', 'Summer Venue', 'Fall Venue'
    ]
    availability_options = ['Full-Year', 'Seasonal']

    if request.method == 'POST':
        if has_bookings:
            messages.error(request, "Cannot edit this venue. It has active bookings.")
            return redirect('users:vendor_dashboard')

        name = request.POST.get('name', '').strip()
        status = request.POST.get('status', 'Active')
        rate = request.POST.get('rate', '').strip()
        street = request.POST.get('street', '').strip()
        city = request.POST.get('city', '').strip()
        province = request.POST.get('province', '').strip()
        postal_code = request.POST.get('postal_code', '').strip().upper()
        selected_categories = request.POST.getlist('categories')
        availability = request.POST.get('availability_type', 'Full-Year')

        # loading image information from the database
        image = request.FILES.get('image')
        current_image_url = row[8]

        if re.match(r'^[A-Z]\d[A-Z]\d[A-Z]\d$', postal_code):
            postal_code = f"{postal_code[:3]} {postal_code[3:]}"

        field_errors = {}
        if not name:
            field_errors['name'] = "Venue name is required."
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
                'image_url': current_image_url
            }
            return render(request, 'vendor/edit_posting.html', {
                'venue': venue,
                'provinces': provinces,
                'all_categories': all_categories,
                'availability_options': availability_options,
                'field_errors': field_errors
            })

        try:
            image_url = current_image_url  # Default to current image
            
            if image:  # If new image was uploaded
                # Create media directory if it doesn't exist
                os.makedirs('media', exist_ok=True)
                
                # Generate a safe filename
                original_name = image.name.replace(' ', '_')
                timestamp = str(int(time.time()))
                filename = f"venue_{timestamp}_{original_name}"
                
                # Save file to media directory
                with open(f'media/{filename}', 'wb+') as destination:
                    for chunk in image.chunks():
                        destination.write(chunk)
                
                # Store relative path in database
                image_url = f'/media/{filename}'

            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE venue
                    SET name=%s, status=%s, rate=%s, street=%s, city=%s,
                        province=%s, postal_code=%s, image_url=%s
                    WHERE venue_id = %s
                """, [name, status, float(rate), street, city, province, postal_code, image_url, venue_id])

                cursor.execute("DELETE FROM venue_category WHERE venue_id = %s", [venue_id])
                for category in selected_categories:
                    cursor.execute("""
                        INSERT INTO venue_category (venue_id, category, availability_type)
                        VALUES (%s, %s, %s)
                    """, [venue_id, category, availability])

            messages.success(request, "Venue updated successfully.")
            return redirect('users:vendor_dashboard')

        except Exception as e:
            messages.error(request, "Failed to update venue.")
            print(f"[DEBUG] Venue update error: {e}")

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
        'image_url': row[8]  # Include image_url in the venue data
    }

    return render(request, 'vendor/edit_posting.html', {
        'venue': venue,
        'provinces': provinces,
        'all_categories': all_categories,
        'availability_options': availability_options
    })


def delete_venue(request, venue_id):
    user_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("SELECT user_id, image_url FROM venue WHERE venue_id = %s", [venue_id])
        row = cursor.fetchone()

    if not row or row[0] != user_id:
        messages.error(request, "Unauthorized access or venue not found.")
        return redirect('users:vendor_dashboard')

    # Prevent deletion if bookings exist
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM booking WHERE venue_id = %s", [venue_id])
        has_bookings = cursor.fetchone()[0] > 0

    if has_bookings:
        messages.error(request, "Cannot delete venue with existing bookings.")
        return redirect('users:vendor_dashboard')

    try:
        if row[1]:
            image_path = os.path.join(settings.MEDIA_ROOT, row[1].split('/media/')[-1])
            if os.path.exists(image_path):
                os.remove(image_path)

        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM venue WHERE venue_id = %s", [venue_id])

        messages.success(request, "Venue deleted successfully.")
    except Exception as e:
        messages.error(request, "Error deleting venue.")
        print(f"[DEBUG] Venue delete error: {e}")

    return redirect('users:vendor_dashboard')
