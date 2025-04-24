# VenueBooker

A simple web application for booking venues.

## Quick Start

1. **Install Requirements**
   ```bash
   # Clone the repository
   git clone git@github.com:alisha-malik/VenueBooker.git
   cd into project folder

   # Create virtual environment Mac
   python3 -m venv venv or python -m venv venv
   source venv/bin/activate

   # Create virtual environment Windows
   python3 -m venv venv or python -m venv venv
   venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Run the Server**
   ```bash
   python manage.py runserver
   ```

3. **Open in Browser**
   ```
   http://127.0.0.1:8000/
   ```

## Access Points

### User URLs
- **Client/Vendor Login**: `http://127.0.0.1:8000/users/login/`
- **Client Dashboard**: `http://127.0.0.1:8000/users/client/dashboard/`
- **Vendor Dashboard**: `http://127.0.0.1:8000/users/vendor/dashboard/`

### Admin URLs
- **Admin Login**: `http://127.0.0.1:8000/users/admin_login/`
- **Admin Dashboard**: `http://127.0.0.1:8000/users/admin/dashboard/`

### Default Admin Credentials
```
Email: admin@gmail.com
Password: Password123
```

## User Types

- **Clients**: Browse and book venues
- **Vendors**: List and manage venues
- **Admins**: Manage users and venues

## Requirements

- Python 3.x
- Git
- Virtualenv 
