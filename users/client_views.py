from django.shortcuts import render, redirect
from django.db import connection
from django.contrib.auth.decorators import login_required
from django.contrib import messages

@login_required(login_url='users:login')
def client_dashboard(request):
    user_id = request.session.get('user_id')
    
    if not user_id:
        messages.error(request, "You must be logged in to view this page.")
        return redirect('users:login')
    
    try:
        print(f"[DEBUG] Logged in user_id: {user_id}", flush=True)

        # Get client name for display in dashboard
        with connection.cursor() as cursor:
            cursor.execute("SELECT name FROM users WHERE user_id = %s", [user_id])
            result = cursor.fetchone()
            client_name = result[0] if result else "Client"
            print(f"[DEBUG] Client name: {client_name}", flush=True)
        
        # Fetch all available venues
        venues = []
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT v.venue_id, v.name, v.rate, v.status, v.image_url, v.description,
                v.capacity, GROUP_CONCAT(vc.category), vc.availability_type
                FROM venue v
                LEFT JOIN venue_category vc ON v.venue_id = vc.venue_id
                WHERE v.status = 'Active'
                GROUP BY v.venue_id, vc.availability_type
                ORDER BY v.name
            """)
            venue_rows = cursor.fetchall()
            print(f"[DEBUG] Number of venues fetched: {len(venue_rows)}", flush=True)

            for row in venue_rows:
                try:
                    print(f"[DEBUG] Processing venue row: {row}", flush=True)
                    image_url = row[4]
                    if image_url:
                        if not image_url.startswith('/media/'):
                            image_url = f'/media/{image_url}'
                        image_url = request.build_absolute_uri(image_url)
                    else:
                        image_url = request.build_absolute_uri('/static/default-placeholder.png')

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
                except Exception as ve:
                    print(f"[DEBUG] Error processing venue row {row}: {ve}", flush=True)
        
        print(f"[DEBUG] Total venues processed: {len(venues)}", flush=True)

        # Get client's booking history
        bookings = []
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT b.booking_id, v.name as venue_name, b.booking_date, 
                       b.start_time, b.end_time, b.status, b.total_amount
                FROM booking b
                JOIN venue v ON b.venue_id = v.venue_id
                WHERE b.user_id = %s
                ORDER BY b.booking_date DESC
            """, [user_id])
            booking_rows = cursor.fetchall()
            print(f"[DEBUG] Number of bookings fetched: {len(booking_rows)}", flush=True)

            for row in booking_rows:
                booking = {
                    'id': row[0],
                    'venue_name': row[1],
                    'date': row[2],
                    'start_time': row[3],
                    'end_time': row[4],
                    'status': row[5],
                    'amount': float(row[6]) if row[6] else 0.0
                }
                bookings.append(booking)
        
        # Get client's messages
        messages_list = []
        with connection.cursor() as cursor:
            cursor.execute("""
                SELECT m.message_id, u.name as sender_name, m.message_text, m.created_at
                FROM message m
                JOIN user u ON m.sender_id = u.user_id
                WHERE m.recipient_id = %s
                ORDER BY m.created_at DESC
            """, [user_id])
            message_rows = cursor.fetchall()
            print(f"[DEBUG] Number of messages fetched: {len(message_rows)}", flush=True)

            for row in message_rows:
                message = {
                    'id': row[0],
                    'sender': row[1],
                    'preview': row[2][:100],
                    'date': row[3].strftime('%b %d, %Y') if row[3] else ''
                }
                messages_list.append(message)
        
        return render(request, 'client/c_dashboard.html', {
            'client_name': client_name,
            'venues': venues,
            'bookings': bookings,
            'messages': messages_list
        })
        
    except Exception as e:
        print(f"[DEBUG] client_dashboard error → {e}", flush=True)
        messages.error(request, "Could not load dashboard.")
        return redirect('users:login')
