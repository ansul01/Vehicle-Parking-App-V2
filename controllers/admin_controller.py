# Parking App V1/controllers/admin_controller.py
from flask import render_template, redirect, url_for, request, flash, jsonify
from flask_login import current_user, login_required
from datetime import datetime, timedelta, date
from models.models import db, User, ParkingLot, ParkingSpot, Reservation, Payment, Transaction, SystemStats
from utils import generate_spot_number, create_spots_for_lot # Changed import path

def init_admin_controller(app):
    """Initializes admin routes with the Flask app."""

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
                            'start_by_id': user_booked.id if user_booked else None,
                            'start_time': reservation.start_time.strftime('%H:%M, %d %b %Y') if reservation else None,
                            'duration': f"{reservation.duration_hours():.1f}h" if reservation else None,
                            'vehicle_number': user_booked.vehicle_number if user_booked else None,
                            'vehicle_type': user_booked.vehicle_type if user_booked else None,
                            'reservation_id': reservation.id if reservation else None
                        })
                    else:
                        row_spots.append(None)
                spot_grid.append(row_spots)
            
            lot_details.append({
                'lot': lot,
                'spot_grid': spot_grid,
                'occupancy_rate': lot.occupancy_rate(),
                'available_spots': lot.available_spots_count()
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