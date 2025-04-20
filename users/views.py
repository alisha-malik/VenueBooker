from django.shortcuts import render, redirect
from django.db import connection
from django.contrib import messages
from django.contrib.auth.hashers import make_password, check_password
from django.contrib.auth.decorators import login_required
from django.contrib.auth import logout
from django.contrib.admin.views.decorators import staff_member_required
from django.shortcuts import render

@staff_member_required
def admin_dashboard(request):
    return render(request, 'users/admin_dashboard.html')


def register(request):
    if request.method == 'POST':
        list(messages.get_messages(request))

        first_name = request.POST.get('first_name', '').strip()
        last_name = request.POST.get('last_name', '').strip()
        phone = request.POST.get('phone', '').strip()
        email = request.POST.get('email', '').lower().strip()
        user_type = request.POST.get('user_type', 'client')
        password = request.POST.get('password', '')

        if not (phone.isdigit() and len(phone) == 10):
            messages.error(request, "Phone must be 10 digits.")
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
                    # Pass along email and user_type to the forgot password page
                    return render(request, 'users/forgot_password.html', {
                        'email': email,
                        'user_type': user_type
                    })

                # Proceed to create account (allowed if email is not registered with same user_type)
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

        with connection.cursor() as cursor:
            try:
                # Fetch by email only, not user_type — we want to validate the type afterward
                cursor.execute("""
                    SELECT user_id, first_name, last_name, phone, email, user_type, password
                    FROM users WHERE email = %s
                """, [email])
                row = cursor.fetchone()

                if row:
                    user_id, first_name, last_name, phone, email, actual_type, hashed_password = row

                    if check_password(password, hashed_password):

                        request.session['user_id'] = user_id
                        request.session['user_type'] = actual_type

                        if actual_type == "Client":
                            return redirect('users:client_dashboard')
                        else:
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


def forgot_password(request):
    if request.method == 'POST':
        email = request.POST.get('email', '').lower().strip()
        user_type = request.POST.get('user_type', '')
        new_password = request.POST.get('new_password', '')
        
        if not email or not user_type or not new_password:
            messages.error(request, "All fields are required.")
            return render(request, 'users/forgot_password.html', {
                'email': email,
                'user_type': user_type
            })
        
        with connection.cursor() as cursor:
            try:
                # First check if the account exists
                cursor.execute("SELECT 1 users WHERE email = %s AND user_type = %s", [email, user_type])
                if not cursor.fetchone():
                    messages.error(request, f"No {user_type} account found with this email.")
                    return render(request, 'users/forgot_password.html', {
                        'email': email,
                        'user_type': user_type
                    })
                
                # Update password
                hashed_password = make_password(new_password)
                cursor.execute("""
                    UPDATE users SET password = %s 
                    WHERE email = %s AND user_type = %s
                """, [hashed_password, email, user_type])
                
                messages.success(request, "Password has been reset! Please log in with your new password.")
                return redirect('users:login')
                
            except Exception as e:
                messages.error(request, "Password reset failed. Please try again.")
                print(f"Password reset error: {str(e)}")
                return render(request, 'users/forgot_password.html', {
                    'email': email,
                    'user_type': user_type
                })
    
    # If GET request or any other scenario, render the form
    # Pre-populate with email and user_type if provided
    email = request.GET.get('email', '')
    user_type = request.GET.get('user_type', '')
    
    return render(request, 'users/forgot_password.html', {
        'email': email,
        'user_type': user_type
    })

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