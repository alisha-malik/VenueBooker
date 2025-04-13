from django.shortcuts import render, redirect
from django.contrib.auth.decorators import login_required

@login_required(login_url='users:login')
def client_dashboard(request):
    user_id = request.session.get('user_id')
        
    return render(request, 'client/c_dashboard.html', {
        'user_id': user_id
    })