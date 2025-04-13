from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages


def vendor_dashboard(request):
    user_id = request.session.get('user_id')
    print(f"DEBUG: Starting vendor_dashboard for user_id: {user_id}", flush=True)

    if not user_id:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('users:login')

    try:
        venues = []
        has_venues = False

        with connection.cursor() as cursor:
            print("DEBUG: Checking if user has more than one venue", flush=True)

            cursor.execute("""
                SELECT user_id, COUNT(*) AS venue_count
                FROM venue
                WHERE user_id = %s
                GROUP BY user_id
                HAVING COUNT(*) > 1
            """, [user_id])
            result = cursor.fetchone()

            if result:
                print("DEBUG: User has more than 1 venue, fetching venue data...", flush=True)

                cursor.execute("""
                    SELECT venue_id, name, rate, status
                    FROM venue
                    WHERE user_id = %s
                    ORDER BY name
                """, [user_id])
                venue_rows = cursor.fetchall()

                venues = [
                    {
                        'id': row[0],
                        'name': row[1],
                        'price': float(row[2]) if row[2] else 0.0,
                        'status': row[3]
                    }
                    for row in venue_rows
                ]
                has_venues = True

            else:
                print("DEBUG: User has 0 or 1 venue — skipping venue fetch", flush=True)

        return render(request, 'vendor/venue_dashboard.html', {
            'venues': venues,
            'has_venues': has_venues
        })

    except Exception as e:
        print(f"DEBUG: vendor_dashboard error → {str(e)}", flush=True)
        messages.error(request, "Could not load dashboard.")
        return redirect('users:login')


def create_posting(request):
    user_id = request.session.get('user_id')

    if not user_id:
        messages.error(request, "You must be logged in to post a venue.")
        return redirect('users:login')

    provinces = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]

    if request.method == 'POST':
        name = request.POST.get('name', '').strip()
        status = request.POST.get('status', 'Active')
        rate = request.POST.get('rate', 0)
        street = request.POST.get('street', '').strip()
        city = request.POST.get('city', '').strip()
        province = request.POST.get('province', '').strip()
        postal_code = request.POST.get('postal_code', '').strip()

        if not all([name, street, city, province, postal_code]):
            messages.error(request, "Please fill in all required fields.")
            return render(request, 'vendor/posting.html', {'provinces': provinces})

        try:
            rate = float(rate)
            if rate <= 0:
                raise ValueError
        except ValueError:
            messages.error(request, "Please enter a valid price.")
            return render(request, 'vendor/posting.html', {'provinces': provinces})

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO venue (name, status, rate, street, city, province, postal_code, user_id)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """, [name, status, rate, street, city, province, postal_code, user_id])

            messages.success(request, f"Venue '{name}' added successfully.")
            return redirect('users:venue_dashboard')

        except Exception as e:
            messages.error(request, "There was an error creating the venue.")
            print(f"[DEBUG] Venue insert error: {e}")
            return render(request, 'vendor/posting.html', {'provinces': provinces})

    return render(request, 'vendor/posting.html', {'provinces': provinces})


def edit_venue(request, venue_id):
    user_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        # Check venue ownership and fetch details
        cursor.execute("""
            SELECT name, status, rate, street, city, province, postal_code, user_id
            FROM venue
            WHERE venue_id = %s
        """, [venue_id])
        row = cursor.fetchone()

    if not row:
        messages.error(request, "Venue not found.")
        return redirect('users:venue_dashboard')

    if row[7] != user_id:
        messages.error(request, "Unauthorized access.")
        return redirect('users:venue_dashboard')

    # Check if venue has bookings
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM booking WHERE venue_id = %s", [venue_id])
        has_bookings = cursor.fetchone()[0] > 0

    provinces = ["AB", "BC", "MB", "NB", "NL", "NS", "NT", "NU", "ON", "PE", "QC", "SK", "YT"]

    if request.method == 'POST':
        if has_bookings:
            messages.error(request, "Cannot edit this venue. It has active bookings.")
            return redirect('users:venue_dashboard')

        name = request.POST.get('name', '').strip()
        status = request.POST.get('status', 'Active')
        rate = request.POST.get('rate', 0)
        street = request.POST.get('street', '').strip()
        city = request.POST.get('city', '').strip()
        province = request.POST.get('province', '').strip()
        postal_code = request.POST.get('postal_code', '').strip()

        try:
            with connection.cursor() as cursor:
                cursor.execute("""
                    UPDATE venue
                    SET name=%s, status=%s, rate=%s, street=%s, city=%s, province=%s, postal_code=%s
                    WHERE venue_id = %s
                """, [name, status, rate, street, city, province, postal_code, venue_id])

            messages.success(request, "Venue updated successfully.")
            return redirect('users:venue_dashboard')

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
        'has_bookings': has_bookings
    }

    return render(request, 'vendor/edit_posting.html', {'venue': venue, 'provinces': provinces})


def delete_venue(request, venue_id):
    user_id = request.session.get('user_id')

    with connection.cursor() as cursor:
        cursor.execute("SELECT user_id FROM venue WHERE venue_id = %s", [venue_id])
        row = cursor.fetchone()

    if not row or row[0] != user_id:
        messages.error(request, "Unauthorized access or venue not found.")
        return redirect('users:venue_dashboard')

    # Prevent deletion if bookings exist
    with connection.cursor() as cursor:
        cursor.execute("SELECT COUNT(*) FROM booking WHERE venue_id = %s", [venue_id])
        has_bookings = cursor.fetchone()[0] > 0

    if has_bookings:
        messages.error(request, "Cannot delete venue with existing bookings.")
        return redirect('users:venue_dashboard')

    try:
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM venue WHERE venue_id = %s", [venue_id])

        messages.success(request, "Venue deleted successfully.")
    except Exception as e:
        messages.error(request, "Error deleting venue.")
        print(f"[DEBUG] Venue delete error: {e}")

    return redirect('users:venue_dashboard')