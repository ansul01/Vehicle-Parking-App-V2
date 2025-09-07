from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from datetime import datetime, timedelta, date # Import date and timedelta

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    # Changed from password_hash to 'password' for consistency with your app.py, but storing hashed
    password = db.Column(db.String(128), nullable=False)
    full_name = db.Column(db.String(120), nullable=True)
    phone = db.Column(db.String(20), nullable=True) # Used 'phone' in app.py
    role = db.Column(db.String(20), default='user', nullable=False) # 'user' or 'admin'
    balance = db.Column(db.Float, default=0.0, nullable=False) # Wallet balance
    vehicle_number = db.Column(db.String(20), nullable=True)
    vehicle_type = db.Column(db.String(20), default='car', nullable=False)

    reservations = db.relationship('Reservation', backref='user', lazy=True)
    payments = db.relationship('Payment', backref='user', lazy=True)
    transactions = db.relationship('Transaction', backref='user', lazy=True)

    def set_password(self, password):
        self.password = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password, password)

    def get_id(self):
        return str(self.id)

    def __repr__(self):
        return f'<User {self.username}>'

class ParkingLot(db.Model):
    __tablename__ = 'parking_lots'
    id = db.Column(db.Integer, primary_key=True)
    prime_location_name = db.Column(db.String(100), nullable=False)
    address = db.Column(db.String(255), nullable=False)
    pin_code = db.Column(db.String(10), nullable=False) # Added pin_code
    price_per_hour = db.Column(db.Float, nullable=False) # Changed from hourly_rate
    layout_rows = db.Column(db.Integer, default=0, nullable=False) # For grid layout
    layout_cols = db.Column(db.Integer, default=0, nullable=False) # For grid layout
    max_spots = db.Column(db.Integer, default=0, nullable=False) # Total spots based on layout
    max_parking_limit = db.Column(db.Integer, default=100, nullable=False) # Overall max limit

    # Features
    has_security = db.Column(db.Boolean, default=False)
    has_lighting = db.Column(db.Boolean, default=False)
    is_covered = db.Column(db.Boolean, default=False)

    parking_spots = db.relationship('ParkingSpot', backref='lot', lazy=True, cascade="all, delete-orphan") # Renamed to 'lot'

    def total_occupied_spots(self):
        return ParkingSpot.query.filter_by(lot_id=self.id, status='O').count()

    def available_spots_count(self):
        return self.max_spots - self.total_occupied_spots()

    def occupancy_rate(self):
        if self.max_spots == 0:
            return 0.0
        return (self.total_occupied_spots() / self.max_spots) * 100

    def __repr__(self):
        return f'<ParkingLot {self.prime_location_name}>'

class ParkingSpot(db.Model):
    __tablename__ = 'parking_spots'
    id = db.Column(db.Integer, primary_key=True)
    lot_id = db.Column(db.Integer, db.ForeignKey('parking_lots.id'), nullable=False) # Changed to lot_id
    spot_number = db.Column(db.String(10), nullable=False)
    row_position = db.Column(db.Integer, nullable=False) # For grid layout
    col_position = db.Column(db.Integer, nullable=False) # For grid layout
    status = db.Column(db.String(1), default='A', nullable=False) # A: Available, O: Occupied, M: Maintenance

    reservations = db.relationship('Reservation', backref='spot', lazy=True) # Renamed to 'spot'

    def current_reservation(self):
        """Returns the active reservation for this spot, if any."""
        return Reservation.query.filter_by(spot_id=self.id, end_time=None).first()

    def __repr__(self):
        return f'<ParkingSpot {self.spot_number} at {self.lot.prime_location_name}>'

class Reservation(db.Model):
    __tablename__ = 'reservations'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    spot_id = db.Column(db.Integer, db.ForeignKey('parking_spots.id'), nullable=False) # Changed to spot_id
    start_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    end_time = db.Column(db.DateTime, nullable=True) # Nullable for active reservations
    cost = db.Column(db.Float, nullable=True) # Total cost of the reservation
    status = db.Column(db.String(20), default='active', nullable=False) # 'active', 'completed', 'cancelled'
    vehicle_number = db.Column(db.String(20), nullable=True) # Stored in reservation for historical data

    def duration_hours(self):
        """Calculate duration in hours."""
        if self.start_time and self.end_time:
            duration = self.end_time - self.start_time
            return duration.total_seconds() / 3600
        elif self.start_time:
            # For active reservation, calculate duration up to now
            duration = datetime.utcnow() - self.start_time
            return duration.total_seconds() / 3600
        return 0.0

    def __repr__(self):
        return f'<Reservation {self.id} for {self.user.username} at {self.spot.spot_number}>'

class Payment(db.Model):
    __tablename__ = 'payments'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    reservation_id = db.Column(db.Integer, db.ForeignKey('reservations.id'), nullable=True)
    amount = db.Column(db.Float, nullable=False)
    payment_date = db.Column(db.DateTime, default=datetime.utcnow) # Changed from payment_date
    payment_method = db.Column(db.String(50), nullable=False)
    payment_status = db.Column(db.String(20), default='pending', nullable=False) # 'completed', 'pending', 'failed'
    completed_at = db.Column(db.DateTime, nullable=True) # Timestamp for when payment was completed

    def __repr__(self):
        return f'<Payment {self.id} for {self.user.username} amount {self.amount}>'

class Transaction(db.Model):
    __tablename__ = 'transactions'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    type = db.Column(db.String(50), nullable=False) # e.g., 'credit', 'debit', 'reservation_payment'
    created_at = db.Column(db.DateTime, default=datetime.utcnow) # Changed from 'date' to 'created_at'
    description = db.Column(db.String(255), nullable=True)
    reference_id = db.Column(db.String(100), unique=True, nullable=True) # For external transaction IDs
    payment_method = db.Column(db.String(50), nullable=True) # e.g., 'wallet', 'credit_card', 'bank_transfer'
    status = db.Column(db.String(20), default='completed', nullable=False) # e.g., 'completed', 'pending', 'failed'

    def __repr__(self):
        return f'<Transaction {self.id} type {self.type} amount {self.amount}>'

class SystemStats(db.Model):
    __tablename__ = 'system_stats'
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.Date, unique=True, nullable=False, default=date.today)
    total_revenue = db.Column(db.Float, default=0.0)
    total_reservations = db.Column(db.Integer, default=0)
    average_occupancy_rate = db.Column(db.Float, default=0.0)

    def __repr__(self):
        return f'<SystemStats {self.date} revenue {self.total_revenue}>'