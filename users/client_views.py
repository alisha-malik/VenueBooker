from django.shortcuts import render, redirect
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.contrib import messages
import sys
        
def client_dashboard(request):
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
                GROUP BY v.venue_id, vc.availability_type
                ORDER BY v.name
            """,)

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
                    'categories': row[7].split(',') if row[7] else [],
                    'availability': row[8] or 'Full-Year'
                }
                venues.append(venue)

        has_venues = len(venues) > 0

        return render(request, 'client/c_dashboard.html', {
            'venues': venues,
            'has_venues': has_venues
        })

    except Exception as e:
        print(f"[DEBUG] client_dashboard error → {e}", flush=True)
        messages.error(request, "Could not load dashboard.")
        return redirect('users:login')
    
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