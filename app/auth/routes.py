from flask import render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db
from app.auth import bp
from app.models import User

@bp.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        user = User.query.filter_by(username=username).first()
        if user is None or not check_password_hash(user.password_hash, password):
            flash('Invalid username or password', 'error')
            return redirect(url_for('auth.login'))
        login_user(user, remember=request.form.get('remember_me'))
        # If user has no org memberships, send them to create one
        if user.memberships.count() == 0:
            return redirect(url_for('organizations.create'))
        return redirect(url_for('main.index'))
    return render_template('auth/login.html')

@bp.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('auth.login'))

@bp.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('main.index'))
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        confirm_password = request.form.get('confirm_password')

        from email_validator import validate_email, EmailNotValidError
        try:
            valid = validate_email(email)
            email = valid.email
        except EmailNotValidError as e:
            flash(str(e), 'error')
            return render_template('auth/register.html')

        # Check uniqueness
        if User.query.filter_by(username=username).first():
            flash('Username already taken.', 'error')
            return redirect(url_for('auth.register'))
        if User.query.filter_by(email=email).first():
            flash('Email already registered.', 'error')
            return redirect(url_for('auth.register'))

        user = User(username=username, email=email, password_hash=generate_password_hash(password))
        db.session.add(user)
        db.session.commit()

        # Check for pending invitations
        from app.models import PendingInvitation, Membership
        invitations = PendingInvitation.query.filter_by(email=email).all()
        org_joined = False
        for inv in invitations:
            m = Membership(user_id=user.id, organization_id=inv.organization_id, role=inv.role)
            db.session.add(m)
            db.session.delete(inv)
            org_joined = True
            
        if org_joined:
            db.session.commit()

        # Auto-login after registration
        login_user(user)
        flash('Welcome! Your account has been created.', 'success')
        
        if org_joined:
            return redirect(url_for('main.index'))
        else:
            return redirect(url_for('organizations.create'))
    
    # Pre-fill email from token if provided
    prefill_email = request.args.get('email', '')
    return render_template('auth/register.html', prefill_email=prefill_email)
