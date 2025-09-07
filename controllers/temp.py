from flask import Flask, render_template, redirect, url_for, request, session, flash, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, current_user, login_required
from werkzeug.security import generate_password_hash, check_password_hash
from datetime import datetime, timedelta, date
import json
import time
import uuid

from models.models import db, User, ParkingLot, ParkingSpot, Reservation, Payment, Transaction, SystemStats

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

# ---------------- Utility Functions ----------------
def generate_spot_number(row, col):
    return f"{chr(65 + row)}{col + 1}"

def create_spots_for_lot(lot):
    for row in range(lot.layout_rows):
        for col in range(lot.layout_cols):
            spot_number = generate_spot_number(row, col)
            spot = ParkingSpot(
                lot_id=lot.id,
                spot_number=spot_number,
                row_position=row,
                col_position=col,
                status='A'
            )
            db.session.add(spot)

def create_transaction(user_id, amount, transaction_type, description, reference_id=None, payment_method=None, status='completed'):
    try:
        if not reference_id:
            reference_id = f"{transaction_type.upper()}_{int(time.time())}_{uuid.uuid4().hex[:8].upper()}"

        transaction = Transaction(
            user_id=user_id,
            amount=amount,
            type=transaction_type,
            description=description,
            reference_id=reference_id,
            payment_method=payment_method,
            status=status
        )

        db.session.add(transaction)
        return transaction
    except Exception as e:
        print(f"Error creating transaction: {e}")
        return None

# ---------------- Routes ----------------

@app.route('/')
def home():
    if current_user.is_authenticated:
        if current_user.role == 'admin':
            return redirect(url_for('admin_dashboard'))
        else:
            return redirect(url_for('user_dashboard'))
    return render_template('login.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        flash("You are already logged in!", "info")
        return redirect(url_for('user_dashboard')) # Or your default dashboard

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password): # Assuming you have a check_password method in your User model
            login_user(user, remember=remember)
            flash(f"Welcome back, {user.username}!", "success")
            # Redirect based on role or to a common dashboard
            if user.role == 'user':
                return redirect(url_for('user_dashboard'))
            elif user.role == 'owner':
                return redirect(url_for('owner_dashboard'))
            elif user.role == 'admin':
                return redirect(url_for('admin_dashboard'))
            else:
                return redirect(url_for('home')) # Fallback
        else:
            flash('Invalid username or password', 'danger')

    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        flash("You are already registered and logged in!", "info")
        return redirect(url_for('user_dashboard')) # Or your default dashboard

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')
        role = request.form.get('role') # 'user' or 'owner'

        if password != confirm_password:
            flash("Passwords do not match!", "danger")
            return redirect(url_for('register'))

        if User.query.filter_by(username=username).first():
            flash("Username already taken. Please choose another.", "danger")
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash("Email already registered. Please use another.", "danger")
            return redirect(url_for('register'))

        try:
            new_user = User(username=username, email=email, role=role)
            new_user.set_password(password) # Assuming you have a set_password method in your User model
            db.session.add(new_user)
            db.session.commit()
            flash("Registration successful! You can now log in.", "success")
            return redirect(url_for('login'))
        except Exception as e:
            db.session.rollback()
            flash(f"Registration failed: {str(e)}", "danger")

    return render_template('register.html')

# Don't forget your logout route if you removed it earlier
@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for('login'))

@app.route('/admin/dashboard')
@login_required
def admin_dashboard():
    if current_user.role != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))

    lots = ParkingLot.query.all()
    users = User.query.filter_by(role='user').all()
    total_revenue = db.session.query(db.func.sum(Payment.amount)).filter_by(payment_status='completed').scalar() or 0
    total_bookings = Reservation.query.count()
    
    lot_details = []
    for lot in lots:
        spots = ParkingSpot.query.filter_by(lot_id=lot.id).order_by(ParkingSpot.row_position, ParkingSpot.col_position).all()
        
        spot_grid = []
        for row in range(lot.layout_rows):
            row_spots = []
            for col in range(lot.layout_cols):
                spot = next((s for s in spots if s.row_position == row and s.col_position == col), None)
                if spot:
                    reservation = spot.current_reservation()
                    user_booked = User.query.get(reservation.user_id) if reservation else None
                    row_spots.append({
                        'spot': spot,
                        'occupied_by': user_booked.username if user_booked else None,
                        'start_by_id': user_booked.id if user_booked else None, # Added user ID
                        'start_time': reservation.start_time.strftime('%H:%M, %d %b %Y') if reservation else None, # More detailed time
                        'duration': f"{reservation.duration_hours():.1f}h" if reservation else None,
                        'vehicle_number': user_booked.vehicle_number if user_booked else None, # Added
                        'vehicle_type': user_booked.vehicle_type if user_booked else None,     # Added
                        'reservation_id': reservation.id if reservation else None # Added
                    })
                else:
                    row_spots.append(None)
            spot_grid.append(row_spots)
        
        lot_details.append({
            'lot': lot,
            'spot_grid': spot_grid,
            'occupancy_rate': lot.occupancy_rate(),
            'available_spots': lot.available_spots_count() # Fix: Use the method
        })
    
    return render_template('admin_dashboard.html', 
                           lot_details=lot_details, 
                           users=users,
                           total_revenue=total_revenue,
                           total_bookings=total_bookings)

@app.route('/admin/analytics')
@login_required
def admin_analytics():
    if current_user.role != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))
    
    end_date = datetime.now().date()
    start_date = end_date - timedelta(days=30)
    
    daily_revenue = db.session.query(
        db.func.date(Payment.completed_at).label('date'),
        db.func.sum(Payment.amount).label('revenue')
    ).filter(
        Payment.payment_status == 'completed',
        Payment.completed_at >= start_date
    ).group_by(db.func.date(Payment.completed_at)).all()
    
    peak_hours = db.session.query(
        db.func.strftime('%H', Reservation.start_time).label('hour'),
        db.func.count(Reservation.id).label('bookings')
    ).group_by(db.func.strftime('%H', Reservation.start_time)).all()
    
    lot_occupancy = []
    for lot in ParkingLot.query.all():
        lot_occupancy.append({
            'name': lot.prime_location_name,
            'occupancy': lot.occupancy_rate()
        })
    
    return render_template('admin_analytics.html',
                           daily_revenue=daily_revenue,
                           peak_hours=peak_hours,
                           lot_occupancy=lot_occupancy)

@app.route('/admin/create_lot', methods=['POST'])
@login_required
def create_lot():
    if current_user.role != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))

    try:
        name = request.form.get('prime_location_name')
        price = float(request.form.get('price_per_hour'))
        address = request.form.get('address')
        pin_code = request.form.get('pin_code')
        layout_rows = int(request.form.get('layout_rows', 4))
        layout_cols = int(request.form.get('layout_cols', 5))
        max_parking_limit = int(request.form.get('max_parking_limit', 100))
        
        has_security = 'has_security' in request.form
        has_lighting = 'has_lighting' in request.form
        is_covered = 'is_covered' in request.form
        
        if not all([name, price, address, pin_code]):
            flash("All required fields must be filled!", "danger")
            return redirect(url_for('admin_dashboard'))

        calculated_max_spots = layout_rows * layout_cols

        if calculated_max_spots > max_parking_limit:
            flash(f"Current layout ({calculated_max_spots} spots) exceeds maximum parking limit ({max_parking_limit})!", "danger")
            return redirect(url_for('admin_dashboard'))

        new_lot = ParkingLot(
            prime_location_name=name,
            price_per_hour=price,
            address=address,
            pin_code=pin_code,
            max_spots=calculated_max_spots,
            layout_rows=layout_rows,
            layout_cols=layout_cols,
            max_parking_limit=max_parking_limit,
            has_security=has_security,
            has_lighting=has_lighting,
            is_covered=is_covered
        )
        
        db.session.add(new_lot)
        db.session.commit()

        create_spots_for_lot(new_lot)
        db.session.commit()
        
        flash(f"Parking lot '{name}' created successfully with {calculated_max_spots} spots (Max limit: {max_parking_limit})!", "success")

    except ValueError:
        flash("Invalid input format for numbers!", "danger")
        db.session.rollback()
    except Exception as e:
        flash(f"Error creating parking lot: {str(e)}", "danger")
        db.session.rollback()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/admin/delete_lot/<int:lot_id>', methods=['POST'])
@login_required
def delete_lot(lot_id):
    if current_user.role != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))

    lot = ParkingLot.query.get(lot_id)
    if not lot:
        flash("Parking lot not found!", "danger")
        return redirect(url_for('admin_dashboard'))

    if any(spot.status == 'O' for spot in lot.parking_spots):
        flash("Cannot delete a lot with occupied spots!", "danger")
        return redirect(url_for('admin_dashboard'))

    try:
        db.session.delete(lot)
        db.session.commit()
        flash("Parking lot and its spots deleted successfully!", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error deleting parking lot: {str(e)}", "danger")

    return redirect(url_for('admin_dashboard'))

@app.route('/admin/update_lot', methods=['POST'])
@login_required
def update_lot():
    if current_user.role != 'admin':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))
    
    try:
        lot_id = request.form['lot_id']
        lot = ParkingLot.query.get(lot_id)
        
        if not lot:
            flash("Parking lot not found!", "danger")
            return redirect(url_for('admin_dashboard'))
        
        lot.prime_location_name = request.form['prime_location_name']
        lot.price_per_hour = float(request.form['price_per_hour'])
        lot.address = request.form['address']
        lot.pin_code = request.form['pin_code']
        
        new_layout_rows = int(request.form.get('layout_rows', lot.layout_rows))
        new_layout_cols = int(request.form.get('layout_cols', lot.layout_cols))
        new_max_spots = new_layout_rows * new_layout_cols
        new_max_parking_limit = int(request.form.get('max_parking_limit', lot.max_parking_limit))

        lot.has_security = 'has_security' in request.form
        lot.has_lighting = 'has_lighting' in request.form
        lot.is_covered = 'is_covered' in request.form
        
        if new_max_spots > new_max_parking_limit:
            flash(f"Cannot set {new_max_spots} spots as it exceeds maximum parking limit ({new_max_parking_limit})!", "danger")
            return redirect(url_for('admin_dashboard'))
        
        current_spots_count = len(lot.parking_spots)
        
        if new_max_spots > current_spots_count:
            for i in range(current_spots_count, new_max_spots):
                row = i // new_layout_cols
                col = i % new_layout_cols
                spot_number = generate_spot_number(row, col)
                
                new_spot = ParkingSpot(
                    lot_id=lot.id,
                    spot_number=spot_number,
                    row_position=row,
                    col_position=col,
                    status='A'
                )
                db.session.add(new_spot)
        elif new_max_spots < current_spots_count:
            spots_to_remove = ParkingSpot.query.filter_by(lot_id=lot.id).order_by(ParkingSpot.id.desc()).limit(current_spots_count - new_max_spots).all()
            for spot in spots_to_remove:
                if spot.status == 'O':
                    flash("Cannot reduce spots while some are occupied!", "danger")
                    return redirect(url_for('admin_dashboard'))
                db.session.delete(spot)
        
        lot.layout_rows = new_layout_rows
        lot.layout_cols = new_layout_cols
        lot.max_spots = new_max_spots
        lot.max_parking_limit = new_max_parking_limit
        
        db.session.commit()
        flash(f"Parking lot updated successfully! Current: {new_max_spots} spots, Max limit: {new_max_parking_limit}", "success")
        
    except ValueError:
        flash("Invalid input format for numbers!", "danger")
        db.session.rollback()
    except Exception as e:
        flash(f"Error updating parking lot: {str(e)}", "danger")
        db.session.rollback()
    
    return redirect(url_for('admin_dashboard'))

@app.route('/user/dashboard')
@login_required
def user_dashboard():
    if current_user.role != 'user':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))

    user = current_user
    lots = ParkingLot.query.all()
    reservations = Reservation.query.filter_by(user_id=user.id).order_by(Reservation.start_time.desc()).all()
    
    active_reservations = [res for res in reservations if res.end_time is None]
    past_reservations = [res for res in reservations if res.end_time is not None][:10]
    
    total_spent = sum(res.cost for res in past_reservations if res.cost is not None) # Handle None for cost
    total_hours = sum(res.duration_hours() for res in past_reservations)
    
    return render_template('user_dashboard.html', 
                           user=user,
                           lots=lots, 
                           active_reservations=active_reservations,
                           past_reservations=past_reservations,
                           total_spent=total_spent,
                           total_hours=total_hours)

@app.route('/user/profile', methods=['GET', 'POST'])
@login_required
def user_profile():
    return render_template('user_profile.html', user=current_user)

@app.route('/user/edit_profile', methods=['GET', 'POST'])
@login_required
def edit_profile():
    user = current_user
    if request.method == 'POST':
        user.username = request.form.get('username')
        user.email = request.form.get('email')
        user.full_name = request.form.get('full_name')
        user.phone = request.form.get('phone')
        user.vehicle_number = request.form.get('vehicle_number')
        user.vehicle_type = request.form.get('vehicle_type')

        try:
            db.session.commit()
            flash('Profile updated successfully!', 'success')
            return redirect(url_for('user_profile'))
        except Exception as e:
            db.session.rollback()
            flash(f'Error updating profile: {e}', 'danger')
            return render_template('edit_profile.html', user=user)

    return render_template('edit_profile.html', user=user)

@app.route('/user/change_password', methods=['GET', 'POST'])
@login_required
def change_password():
    if request.method == 'POST':
        old_password = request.form.get('old_password')
        new_password = request.form.get('new_password')
        confirm_new_password = request.form.get('confirm_new_password')

        if not current_user.check_password(old_password):
            flash('Incorrect old password.', 'danger')
        elif new_password != confirm_new_password:
            flash('New passwords do not match.', 'danger')
        else:
            current_user.set_password(new_password)
            db.session.commit()
            flash('Password changed successfully!', 'success')
            return redirect(url_for('user_profile'))
    return render_template('change_password.html')


@app.route('/user/wallet')
@login_required
def user_wallet():
    user_transactions = Transaction.query.filter_by(user_id=current_user.id).order_by(Transaction.created_at.desc()).all()

    total_spent = sum(t.amount for t in user_transactions if t.type in ['debit', 'reservation_payment'])
    total_added = sum(t.amount for t in user_transactions if t.type == 'credit')

    return render_template('user_wallet.html',
                           user=current_user,
                           transactions=user_transactions,
                           total_spent=total_spent, # This is explicitly passed
                           total_added=total_added)  # This is explicitly passed

@app.route('/add_money', methods=['POST'])
@login_required
def add_money():
    if current_user.role != 'user':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))
    
    try:
        amount = float(request.form.get('amount', 0))
        payment_method = request.form.get('payment_method', '')
        
        if amount < 10:
            flash("Minimum amount to add is ₹10", "danger")
            return redirect(url_for('user_wallet'))
        
        if amount > 10000:
            flash("Maximum amount to add is ₹10,000", "danger")
            return redirect(url_for('user_wallet'))
        
        if not payment_method:
            flash("Please select a payment method", "danger")
            return redirect(url_for('user_wallet'))
        
        user = current_user
        user.balance += amount
        
        create_transaction(
            user_id=user.id,
            amount=amount,
            transaction_type='credit', # Changed 'type' to 'transaction_type'
            description=f"Money added via {payment_method.title()}",
            payment_method=payment_method,
            status='completed'
        )
        
        db.session.commit()
        
        flash(f"₹{amount:.2f} successfully added to your wallet!", "success")
        
    except ValueError:
        flash("Invalid amount entered", "danger")
    except Exception as e:
        flash(f"Failed to add money: {str(e)}. Please try again.", "danger")
        db.session.rollback()
    
    return redirect(url_for('user_wallet'))

@app.route('/withdraw_money', methods=['POST'])
@login_required
def withdraw_money():
    if current_user.role != 'user':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))
    
    try:
        amount = float(request.form.get('amount', 0))
        bank_account = request.form.get('bank_account', '')
        
        user = current_user
        current_balance = user.balance
        
        if amount < 50:
            flash("Minimum withdrawal amount is ₹50", "danger")
            return redirect(url_for('user_wallet'))
        
        if amount > current_balance:
            flash("Insufficient balance for withdrawal", "danger")
            return redirect(url_for('user_wallet'))
        
        if not bank_account:
            flash("Please provide bank account details.", "danger")
            return redirect(url_for('user_wallet'))
        
        user.balance -= amount
        
        create_transaction(
            user_id=user.id,
            amount=amount,
            transaction_type='debit', # Changed 'type' to 'transaction_type'
            description=f"Money withdrawn to {bank_account} account",
            payment_method='bank_transfer',
            status='pending'
        )
        
        db.session.commit()
        
        flash(f"₹{amount:.2f} withdrawal request submitted successfully!", "success")
        
    except ValueError:
        flash("Invalid amount entered", "danger")
    except Exception as e:
        flash(f"Failed to process withdrawal: {str(e)}. Please try again.", "danger")
        db.session.rollback()
    
    return redirect(url_for('user_wallet'))

@app.route('/api/wallet/balance')
@login_required
def wallet_balance_api():
    return jsonify({'balance': current_user.balance or 0})

@app.route('/book/<int:lot_id>', methods=['POST'])
@login_required
def book_spot(lot_id):
    if current_user.role != 'user':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))

    user = current_user
    lot = ParkingLot.query.get(lot_id)
    
    active_reservation = Reservation.query.filter_by(user_id=user.id, end_time=None).first()
    if active_reservation:
        flash("You already have an active reservation! Please release it before booking a new spot.", "warning")
        return redirect(url_for('user_dashboard'))
    
    spot = ParkingSpot.query.filter_by(lot_id=lot_id, status='A').first()
    if not spot:
        flash("No available spots in this lot!", "danger")
        return redirect(url_for('user_dashboard'))

    estimated_cost = lot.price_per_hour
    if user.balance < estimated_cost:
        flash("Insufficient balance for initial hold. Please add money to your wallet.", "danger")
        return redirect(url_for('user_wallet'))

    try:
        spot.status = 'O'
        reservation = Reservation(
            user_id=user.id, 
            spot_id=spot.id, 
            start_time=datetime.utcnow(),
            vehicle_number=user.vehicle_number,
            status='active'
        )
        db.session.add(reservation)
        db.session.commit()
        
        flash(f"Spot {spot.spot_number} booked successfully at {lot.prime_location_name}! Initial hold of ₹{estimated_cost:.2f} applied.", "success")
    except Exception as e:
        db.session.rollback()
        flash(f"Error booking spot: {str(e)}", "danger")
    
    return redirect(url_for('user_dashboard'))

@app.route('/release/<int:reservation_id>', methods=['POST'])
@login_required
def release_spot(reservation_id):
    if current_user.role != 'user':
        flash("Unauthorized access!", "danger")
        return redirect(url_for('home'))

    try:
        reservation = Reservation.query.get(reservation_id)
        if not reservation or reservation.user_id != current_user.id:
            flash("Reservation not found or unauthorized!", "danger")
            return redirect(url_for('user_dashboard'))

        if reservation.end_time is None:
            user = current_user
            spot = ParkingSpot.query.get(reservation.spot_id)
            
            reservation.end_time = datetime.utcnow()
            duration_hours = reservation.duration_hours()
            cost = round(duration_hours * spot.lot.price_per_hour, 2)
            
            reservation.cost = cost
            reservation.status = 'completed'
            
            spot.status = 'A'
            
            if user.balance >= cost:
                user.balance -= cost
                
                payment = Payment(
                    user_id=user.id,
                    reservation_id=reservation.id,
                    amount=cost,
                    payment_method='wallet',
                    payment_status='completed',
                    completed_at=datetime.utcnow()
                )
                db.session.add(payment)

                create_transaction(
                    user_id=user.id,
                    amount=cost,
                    transaction_type='debit',
                    description=f"Payment for reservation {reservation.id} at {spot.lot.prime_location_name}",
                    payment_method='wallet',
                    status='completed'
                )

                db.session.commit()
                
                flash(f"Spot released! Duration: {duration_hours:.1f}h, Total Cost: ₹{cost:.2f}.", "success")
            else:
                flash(f"Insufficient balance for payment (₹{cost:.2f})! Please add funds immediately to avoid penalties.", "danger")
                reservation.status = 'pending_payment'
                db.session.commit()
                return redirect(url_for('user_wallet'))
        else:
            flash("This reservation was already completed!", "warning")

    except Exception as e:
        db.session.rollback()
        flash(f"Error releasing spot: {str(e)}", "danger")
    
    return redirect(url_for('user_dashboard'))

@app.route('/api/lot/<int:lot_id>/layout')
def get_lot_layout(lot_id):
    lot = ParkingLot.query.get_or_404(lot_id)
    spots = ParkingSpot.query.filter_by(lot_id=lot_id).all()
    
    layout = []
    for row in range(lot.layout_rows):
        row_spots = []
        for col in range(lot.layout_cols):
            spot = next((s for s in spots if s.row_position == row and s.col_position == col), None)
            if spot:
                row_spots.append({
                    'id': spot.id,
                    'number': spot.spot_number,
                    'status': spot.status
                })
            else:
                row_spots.append(None)
        layout.append(row_spots)
    
    return jsonify({
        'layout': layout,
        'occupancy_rate': lot.occupancy_rate()
    })

if __name__ == '__main__':
    app.run(debug=True)