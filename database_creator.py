import os
from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash
import sqlite3
from models.models import db, User  # Import from your models.py

# ---------------- Flask App Setup ----------------
app = Flask(__name__, instance_relative_config=True) # Enable instance_relative_config
app.config.from_mapping(
    SQLALCHEMY_DATABASE_URI=f'sqlite:///{os.path.join(app.instance_path, "parking.db")}',
    SQLALCHEMY_TRACK_MODIFICATIONS=False
)

# Ensure the instance folder exists
# This is crucial for placing the database file within 'instance/'
try:
    os.makedirs(app.instance_path)
except OSError:
    pass # instance folder already exists

# Initialize db with app
db.init_app(app)

# ---------------- Database Migration Function ----------------
def migrate_database():
    """Handle database migration for new columns"""
    try:
        # Connect directly to SQLite to add missing columns
        # Use app.instance_path to ensure connection to the correct DB file
        db_path = os.path.join(app.instance_path, 'parking.db')
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        print("🔄 Checking for database migrations...")
        
        # Check if max_parking_limit column exists
        cursor.execute("PRAGMA table_info(parking_lots)")
        columns = [column[1] for column in cursor.fetchall()]
        
        migrations_applied = False
        
        if 'max_parking_limit' not in columns:
            print("    Adding missing max_parking_limit column...")
            cursor.execute("ALTER TABLE parking_lots ADD COLUMN max_parking_limit INTEGER DEFAULT 100 NOT NULL")
            
            # Update existing rows to set reasonable max_parking_limit values
            cursor.execute("""
                UPDATE parking_lots 
                SET max_parking_limit = CASE 
                    WHEN max_spots > 100 THEN max_spots 
                    ELSE 100 
                END
            """)
            
            migrations_applied = True
            print("    ✅ max_parking_limit column added successfully")
        
        # You can add more migration checks here in the future
        # Example:
        # if 'new_column' not in columns:
        #     cursor.execute("ALTER TABLE parking_lots ADD COLUMN new_column TEXT DEFAULT '' NOT NULL")
        #     migrations_applied = True
        #     print("    ✅ new_column added successfully")
        
        if migrations_applied:
            conn.commit()
            print("✅ Database migrations completed successfully!")
        else:
            print("ℹ️  No migrations needed - database is up to date")
        
        conn.close()
        
    except Exception as e:
        print(f"❌ Migration error: {e}")
        if 'conn' in locals():
            conn.close()

# ---------------- Create DB and Admin ----------------
def setup_database():
    """Complete database setup with migrations and admin user creation"""
    
    print("🚀 Starting database setup...")
    
    # Create all tables
    db.create_all()
    print("✅ Database tables created successfully!")
    
    # Run migrations for existing databases
    migrate_database()
    
    # Create default admin if not exists
    admin_exists = User.query.filter_by(username='admin').first()
    
    if not admin_exists:
        admin = User(
            username='admin',
            email='admin@parking.com',  # Required field in enhanced model
            password=generate_password_hash('admin123'),
            role='admin',
            full_name='System Administrator'
        )
        db.session.add(admin)
        db.session.commit()
        print("✅ Admin user created successfully!")
        print("    Username: admin")
        print("    Password: admin123")
        print("    Email: admin@parking.com")
    else:
        print("ℹ️  Admin user already exists.")
        print("    Username: admin")
        print("    Password: admin123")
        print("    Email: admin@parking.com")
    
    print("🎉 Database setup completed!")
    print("\n" + "="*50)
    print("Your parking management system is ready to use!")
    print("Run your main Flask app now with: python app.py")
    print("="*50)

# ---------------- Run Setup ----------------
if __name__ == '__main__':
    with app.app_context():
        setup_database()