# Vehicle-Parking-App-V2
IITM BS Diploma Level MAD II Project

Vehicle Parking App V2
A comprehensive Flask-based web application for managing and booking parking spots. The system supports user accounts, admin management of parking lots, a user wallet for transactions, and real-time reservation tracking.

Features
User Dashboard
User Authentication: Secure user registration and login.

Profile Management: Users can view and edit their personal information, including full name, phone number, and vehicle details.

Password Management: Users can securely change their passwords.

Parking Spot Booking: Book an available parking spot with an initial hold on the user's wallet balance.

Reservations: View active and past reservations, with real-time tracking of duration and cost for active bookings.

Wallet System: Add and withdraw money from a personal wallet, with a detailed transaction history.

Admin Panel
Parking Lot Management: Admins can create, update, and delete parking lots, defining their layout (rows x columns), price per hour, and features like security and lighting.

Live Occupancy View: The admin dashboard provides a grid view of each parking lot's layout, showing which spots are occupied and by whom.

Analytics: View key statistics such as total revenue, total bookings, and user counts.

User Management: View a list of all registered users and their details.

Technology Stack
Backend: Flask

Database: SQLite (Flask-SQLAlchemy)

User Management: Flask-Login

Styling: Bootstrap 5.3, Font Awesome 6.4

Getting Started
Follow these steps to set up and run the application.

Prerequisites
Python 3.x installed

Git installed

Installation
Clone the repository:

Bash

git clone https://github.com/ansul01/Vehicle-Parking-App-V2
cd Vehicle-Parking-App-V2
Create and activate a virtual environment:

Bash

# On Windows
python -m venv venv
venv\Scripts\activate
# On macOS/Linux
python3 -m venv venv
source venv/bin/activate
Install the required Python libraries:

Bash

pip install Flask Flask-SQLAlchemy Flask-Login Werkzeug
Database Setup
The application uses an SQLite database. The database_creator.py script will set up the database and create a default admin user for you.

Run the script from your project directory:

Bash

python database_creator.py
This will create a parking.db file in the instance/ folder and output the default admin login credentials:

Username: admin

Password: admin123

Email: admin@parking.com

Running the Application
Ensure your virtual environment is active.

Run the main application file:

Bash

python app.py
Open your web browser and navigate to http://127.0.0.1:5000 to access the application.

Usage
Admin Access: Log in with the default admin credentials to access the admin dashboard and manage lots.

User Access: From the login page, you can create a new user account to access the user dashboard and book parking spots.

