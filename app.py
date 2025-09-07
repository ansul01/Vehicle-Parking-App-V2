# Parking App V1/app.py
from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
import json
import time
import uuid

# Import models
from models.models import db, User, ParkingLot, ParkingSpot, Reservation, Payment, Transaction, SystemStats

# Import controllers
from controllers.auth_controller import init_auth_controller
from controllers.admin_controller import init_admin_controller
from controllers.user_controller import init_user_controller

# Import utility functions from utils.py
from utils import generate_spot_number, create_spots_for_lot, create_transaction

# ---------------- Flask App Setup ----------------
app = Flask(__name__)
app.config['SECRET_KEY'] = "YOUR_SUPER_SECRET_KEY_HERE_CHANGE_THIS_IN_PRODUCTION_VERY_IMPORTANT"
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message_category = 'info'

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))

with app.app_context():
    db.create_all()

# ---------------- Utility Functions (these are now in utils.py and imported above) ----------------
# No utility functions here anymore, they are in utils.py

# ---------------- Initialize Controllers ----------------
init_auth_controller(app)
init_admin_controller(app)
init_user_controller(app)

if __name__ == '__main__':
    app.run(debug=True)