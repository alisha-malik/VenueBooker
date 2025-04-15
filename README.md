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


