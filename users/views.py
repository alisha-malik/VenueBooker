from django.shortcuts import render, redirect
from django.contrib.auth import authenticate, login, logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth import get_user_model

User = get_user_model()

def register(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        email = request.POST.get('email')
        phone = request.POST.get('phone')
        first_name = request.POST.get('first_name')
        last_name = request.POST.get('last_name')
        user_type = request.POST.get('user_type')
        password = request.POST.get('password')
        
        # Create user using Django's ORM
        user = User.objects.create_user(
            username=username,
            email=email,
            password=password,  # Django will hash this automatically
            first_name=first_name,
            last_name=last_name,
        )
        
        # If phone and user_type are custom fields in your User model
        if hasattr(User, 'phone'):
            user.phone = phone
        if hasattr(User, 'user_type'):
            user.user_type = user_type
            
        user.save()
        
        return redirect('users:login')
    
    return render(request, 'users/register.html')

def user_login(request):
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        
        # Use Django's authentication system
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            return redirect('users:profile')
        else:
            return render(request, 'users/login.html', {'error': 'Invalid credentials'})
    
    return render(request, 'users/login.html')

@login_required
def profile(request):
    return render(request, 'users/profile.html')

def user_logout(request):
    logout(request)
    return redirect('users:login')