# Parking App V1/utils.py
from models.models import db, ParkingSpot, Transaction # Import necessary models and db
from datetime import datetime
import time
import uuid

def generate_spot_number(row, col):
    """Generates a parking spot number based on row and column."""
    return f"{chr(65 + row)}{col + 1}"

def create_spots_for_lot(lot):
    """Creates parking spots for a given parking lot based on its layout."""
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
    """Creates a new transaction record in the database."""
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