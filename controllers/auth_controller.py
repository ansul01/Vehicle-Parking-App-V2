# Parking App V1/controllers/auth_controller.py
from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, current_user, login_required
from models.models import db, User # Import db and User from models

def init_auth_controller(app):
    """Initializes authentication routes with the Flask app."""

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
            return redirect(url_for('user_dashboard'))

        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            remember = True if request.form.get('remember') else False

            user = User.query.filter_by(username=username).first()

            if user and user.check_password(password):
                login_user(user, remember=remember)
                flash(f"Welcome back, {user.username}!", "success")
                if user.role == 'user':
                    return redirect(url_for('user_dashboard'))
                elif user.role == 'owner':
                    # Assuming 'owner_dashboard' exists, otherwise redirect to a default
                    return redirect(url_for('owner_dashboard'))
                elif user.role == 'admin':
                    return redirect(url_for('admin_dashboard'))
                else:
                    return redirect(url_for('home'))
            else:
                flash('Invalid username or password', 'danger')

        return render_template('login.html')

    @app.route('/register', methods=['GET', 'POST'])
    def register():
        if current_user.is_authenticated:
            flash("You are already registered and logged in!", "info")
            return redirect(url_for('user_dashboard'))

        if request.method == 'POST':
            username = request.form.get('username')
            email = request.form.get('email')
            password = request.form.get('password')
            confirm_password = request.form.get('confirm_password')
            role = request.form.get('role')

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
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                flash("Registration successful! You can now log in.", "success")
                return redirect(url_for('login'))
            except Exception as e:
                db.session.rollback()
                flash(f"Registration failed: {str(e)}", "danger")

        return render_template('register.html')

    @app.route('/logout')
    @login_required
    def logout():
        logout_user()
        flash("You have been logged out.", "info")
        return redirect(url_for('login'))