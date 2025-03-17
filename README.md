# VenueBooker

VenueBooker is a web application that helps users book venues easily. This guide provides steps to set up and run the project on your local machine.

## Prerequisites
Ensure you have the following installed:
- [Python](https://www.python.org/downloads/) (3.x recommended)
- [Git](https://git-scm.com/downloads)
- [Virtualenv](https://virtualenv.pypa.io/en/stable/installation/) (optional but recommended)

## Installation

### 1. Clone the Repository
```bash
git clone git@github.com:alisha-malik/VenueBooker.git
cd VB
```

### 2. Create and Activate a Virtual Environment (Optional but Recommended)
#### On macOS/Linux:
```bash
python3 -m venv venv
source venv/bin/activate
```
#### On Windows:
```bash
python -m venv venv
venv\Scripts\activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

## Running the Server

### 4. Launch the Server
```bash
python manage.py runserver
```
By default, the server will run on **http://127.0.0.1:5000/**.

### 5. Access the Application
Open a browser and go to:
```
http://127.0.0.1:5000/
```

## Troubleshooting
- Ensure all dependencies are installed properly.
- Check if the virtual environment is activated.
- If port **5000** is busy, specify another port:
  ```bash
  python app.py --port 8000
  ```

#Django Event Booking Platform: Backend To-DO

This document outlines the structure and responsibilities of the apps in the Django-based event booking platform. The platform serves two user types: **clients** and **vendors**, with separate interfaces and functionalities for each.

---

## **1. `users` App**
Handles **user authentication** and **user profiles**. Differentiates between **clients** and **vendors**.

### **Responsibilities**
- User registration and login.
- User profile management (e.g., name, email, phone number).
- Account type (client or vendor).
- Authentication and authorization.

### **Models**
- `User`: Custom user model (extends Django's `AbstractUser`).
- `Profile`: Stores additional user information (e.g., phone number, address).

---

## **2. `client` App**
Handles all **client-specific functionality**, including searching, filtering, and booking venues.

### **Responsibilities**
- Client-specific views (e.g., search, filter, book venues).
- Display venue details and availability.
- Booking creation and management.
- Leave reviews for venues.

### **Views**
- `ClientDashboardView`: The main dashboard view for clients.
- `VenueListView`: Displays a list of venues with client-specific filters.
- `VenueDetailView`: Displays detailed information about a venue.
- `BookingCreateView`: Allows clients to create a booking.
- `BookingListView`: Displays a client’s bookings.
- `ReviewCreateView`: Allows clients to leave reviews for venues.

---

## **3. `vendor` App**
Handles all **vendor-specific functionality**, including creating, updating, and managing venues and bookings.

### **Responsibilities**
- Vendor-specific views (e.g., create, update, manage venues).
- Manage bookings and payments.
- View booking statistics and reports.
- Respond to client inquiries.

### **Views**
- `VendorDashboardView`: The main dashboard view for vendors.
- `VenueCreateView`: Allows vendors to create a venue.
- `VenueUpdateView`: Allows vendors to update a venue.
- `BookingListView`: Displays bookings for the vendor’s venues.
- `BookingUpdateView`: Allows vendors to update booking status.
- `RevenueReportView`: Displays revenue reports for the vendor.

---

## **4. `venues` App**
Handles **venue-related data** (e.g., venue details, categories, images). This app is shared between clients and vendors.

### **Responsibilities**
- Venue creation, updating, and deletion.
- Venue details (e.g., name, location, capacity, price, availability).
- Venue categorization (e.g., wedding, corporate, private events).
- Venue images and descriptions.

### **Models**
- `Venue`: Stores venue details (e.g., name, location, capacity, price).
- `VenueCategory`: Stores categories for venues (e.g., wedding, corporate).
- `VenueImage`: Stores images for venues.

---

## **5. `bookings` App**
Handles **booking-related data** (e.g., bookings, payment status). This app is shared between clients and vendors.

### **Responsibilities**
- Booking creation, updating, and cancellation.
- Booking status (e.g., pending, confirmed, canceled).
- Booking details (e.g., venue, client, date, time, price).

### **Models**
- `Booking`: Stores booking details (e.g., venue, client, date, time).
- `BookingStatus`: Stores booking status (e.g., pending, confirmed).

---

## **6. `search` App**
Handles **search and filtering** functionality. This app has different filters for clients and vendors.

### **Responsibilities**
- Advanced search and filtering for venues.
- Different filters for clients (e.g., location, capacity, price) and vendors (e.g., booking status, revenue).
- Display search results with pagination.

### **Views**
- `ClientSearchView`: Displays search results with client-specific filters.
- `VendorSearchView`: Displays search results with vendor-specific filters.

---

## **7. `payments` App**
Handles **payment processing** for bookings.

### **Responsibilities**
- Payment integration (e.g., credit card, debit card).
- Payment status (e.g., pending, completed, failed).
- Transaction records.

### **Models**
- `Payment`: Stores payment details (e.g., booking, amount, status).
- `PaymentMethod`: Stores payment methods (e.g., credit card, debit card).

---

## **8. `notifications` App**
Handles **notifications** for clients and vendors (e.g., booking confirmations, payment reminders).

### **Responsibilities**
- Sending notifications via email or in-app messages.
- Notification types (e.g., booking confirmation, payment reminder).

### **Models**
- `Notification`: Stores notification details (e.g., user, message, status).

---

## **9. `reviews` App**
Handles **reviews and ratings** for venues by clients.

### **Responsibilities**
- Review creation and display.
- Rating system (e.g., 1 to 5 stars).
- Average rating calculation for venues.

### **Models**
- `Review`: Stores review details (e.g., venue, client, rating, comment).

---

## **10. `api` App (Optional)**
Provides a **REST API** for external integrations (e.g., mobile apps, third-party services).

### **Responsibilities**
- Expose endpoints for venues, bookings, payments, etc.
- Authentication for API access.

### **Views**
- Use Django REST Framework to expose existing models.


