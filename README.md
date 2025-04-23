# VenueBooker

A simple web application for booking venues.

## Quick Start

1. **Install Requirements**
   ```bash
   # Clone the repository
   git clone git@github.com:alisha-malik/VenueBooker.git
   cd VB

   # Create virtual environment (recommended)
   python3 -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate

   # Install dependencies
   pip install -r requirements.txt
   ```

2. **Run the Server**
   ```bash
   python manage.py runserver
   ```

3. **Open in Browser**
   ```
   http://127.0.0.1:5000/
   ```

## Access Points

### User URLs
- **Client/Vendor Login**: `/users/login/`
- **Client Dashboard**: `/users/client/dashboard/`
- **Vendor Dashboard**: `/users/vendor/dashboard/`

### Admin URLs
- **Admin Login**: `/users/admin_login/`
- **Admin Dashboard**: `/admin/dashboard/`

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
