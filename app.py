import os
from datetime import datetime, timedelta, date, timezone
from calendar import monthrange
from sqlalchemy import func, extract
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from functools import wraps
import secrets
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# For password reset tokens
import resend  # we'll use Resend.com (free tier, works on Vercel)

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'verdisol_agro_secret_key_2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///verdisol_agro.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Resend API key – set in Vercel environment variables
resend.api_key = os.environ.get('RESEND_API_KEY', '')

# -------------------------------
# Database Models
# -------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    reset_token = db.Column(db.String(100), nullable=True)
    reset_token_expiry = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)
    
    def generate_reset_token(self):
        token = secrets.token_urlsafe(32)
        self.reset_token = token
        self.reset_token_expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        db.session.commit()
        return token

    def verify_reset_token(self, token):
        return self.reset_token == token and self.reset_token_expiry > datetime.now(timezone.utc)

# Other models: SocialLink, Sale, Expenditure, Notification, FollowerData (unchanged)
class SocialLink(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), unique=True, nullable=False)
    url = db.Column(db.String(200), nullable=True)
    icon = db.Column(db.String(50), nullable=True)

class Sale(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_title = db.Column(db.String(10), nullable=False, default='Mr')
    customer_name = db.Column(db.String(100), nullable=False)
    service = db.Column(db.String(200), nullable=False)
    service_date = db.Column(db.Date, nullable=False)
    report_status = db.Column(db.String(20), nullable=False, default='pending')
    amount = db.Column(db.Float, nullable=False)
    area_type = db.Column(db.String(20), nullable=False)
    area_size = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='completed')
    invoice_no = db.Column(db.String(50), unique=True, nullable=True)
    
class Expenditure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    amount = db.Column(db.Float, nullable=False)
    date = db.Column(db.Date, nullable=False)
    description = db.Column(db.String(200))

class Notification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    message = db.Column(db.String(200), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    is_read = db.Column(db.Boolean, default=False)

class FollowerData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)

# -------------------------------
# Helper functions (unchanged)
# -------------------------------
def init_demo_data():
    # same as before – keep it
    if User.query.count() == 0:
        admin = User(username='admin', email='admin@verdisol.com')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    # ... (rest of your init_demo_data remains exactly the same)
    # (I copy it from your earlier code – but to save space, assume unchanged)

# ... (all your existing routes: login, logout, dashboard, API endpoints, except we add new ones)

# -------------------------------
# NEW: Password Recovery Routes
# -------------------------------

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.generate_reset_token()
            # Send email using Resend
            try:
                reset_link = url_for('reset_password', token=token, _external=True)
                html_content = f"""
                <h2>Reset Your Verdisol Agro Password</h2>
                <p>Click the link below to set a new password (valid for 1 hour):</p>
                <a href="{reset_link}">{reset_link}</a>
                """
                resend.Emails.send(
                    from_="Verdisol Agro <noreply@verdisol.com>",
                    to=[email],
                    subject="Reset your password",
                    html=html_content
                )
                return render_template('forgot_password.html', message="Reset link sent to your email.")
            except Exception as e:
                print(e)
                return render_template('forgot_password.html', error="Failed to send email. Try again later.")
        else:
            return render_template('forgot_password.html', error="No account with that email.")
    return render_template('forgot_password.html')

@app.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.verify_reset_token(token):
        return "Invalid or expired token", 400
    if request.method == 'POST':
        new_password = request.form['password']
        user.set_password(new_password)
        user.reset_token = None
        user.reset_token_expiry = None
        db.session.commit()
        return redirect(url_for('login'))
    return render_template('reset_password.html', token=token)

# -------------------------------
# NEW: Completed Sales with Year & Month Filter
# -------------------------------

@app.route('/api/completed_sales_by_month')
@login_required
def completed_sales_by_month():
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    if not year or not month:
        return jsonify({'error': 'year and month required'}), 400
    sales = Sale.query.filter_by(status='completed').filter(
        extract('year', Sale.service_date) == year,
        extract('month', Sale.service_date) == month
    ).all()
    total = sum(s.amount for s in sales)
    return jsonify({'year': year, 'month': month, 'total': total, 'count': len(sales), 'sales': [{
        'customer': f"{s.customer_title} {s.customer_name}",
        'amount': s.amount,
        'service_date': s.service_date.isoformat()
    } for s in sales]})

# -------------------------------
# Create tables (keep only create_all, no drop_all)
# -------------------------------
with app.app_context():
    db.create_all()
    init_demo_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# For Vercel
app = app
