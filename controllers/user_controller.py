# Parking App V1/controllers/user_controller.py
from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import datetime
from models.models import db, User, ParkingLot, ParkingSpot, Reservation, Payment, Transaction
from utils import create_transaction # Changed import path

def init_user_controller(app):
    """Initializes user routes with the Flask app."""

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
        
        total_spent = sum(res.cost for res in past_reservations if res.cost is not None)
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
                               total_spent=total_spent,
                               total_added=total_added)

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
                transaction_type='credit',
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
                transaction_type='debit',
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