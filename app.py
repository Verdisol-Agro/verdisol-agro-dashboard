import os
from datetime import datetime, timedelta, date, timezone
from calendar import monthrange
from sqlalchemy import func, extract
from flask import Flask, render_template, request, redirect, url_for, session, jsonify, abort
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from functools import wraps
import secrets
import resend

app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'verdisol_agro_secret_key_2024')
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL', 'sqlite:///verdisol_agro.db')
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

resend.api_key = os.environ.get('RESEND_API_KEY', '')

# -------------------------------
# Database Models
# -------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)          # NEW: admin flag
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
# Helper Functions
# -------------------------------

def init_demo_data():
    # Only create demo data for non-user tables (sales, expenditures, etc.)
    # NO default admin user is created anymore!
    
    if SocialLink.query.count() == 0:
        platforms = [
            ('twitter', 'https://twitter.com/verdisolagro', 'fab fa-twitter'),
            ('linkedin', 'https://linkedin.com/company/verdisol-agro', 'fab fa-linkedin'),
            ('facebook', 'https://facebook.com/verdisolagro', 'fab fa-facebook'),
            ('instagram', 'https://instagram.com/verdisolagro', 'fab fa-instagram'),
            ('whatsapp', 'https://wa.me/263712345678', 'fab fa-whatsapp')
        ]
        for platform, url, icon in platforms:
            link = SocialLink(platform=platform, url=url, icon=icon)
            db.session.add(link)
        db.session.commit()
    
    if Sale.query.count() == 0:
        import random
        start_date = date(2024, 1, 1)
        end_date = date(2025, 4, 14)
        delta = end_date - start_date
        customers = ['John Doe', 'Jane Smith', 'Peter Green', 'Mary Johnson', 'David Brown', 'Susan White']
        titles = ['Mr', 'Mrs', 'Miss', 'Ms']
        services = ['Soil Testing', 'Crop Advisory', 'Irrigation Setup', 'Fertilizer Supply', 'Drone Survey']
        area_types = ['residential', 'farm', 'plot']
        for i in range(40):
            random_days = random.randint(0, delta.days)
            sale_date = start_date + timedelta(days=random_days)
            amount = round(random.uniform(500, 15000), 2)
            report_status = random.choice(['sent', 'pending'])
            status = 'completed' if report_status == 'sent' else 'pending'
            customer = random.choice(customers)
            title = random.choice(titles)
            service = random.choice(services)
            area_type = random.choice(area_types)
            area_size = round(random.uniform(0.5, 50), 1)
            invoice_no = f"INV-{sale_date.strftime('%Y%m%d')}-{i+100}"
            sale = Sale(
                customer_title=title, customer_name=customer, service=service,
                service_date=sale_date, report_status=report_status, amount=amount,
                area_type=area_type, area_size=area_size, status=status, invoice_no=invoice_no
            )
            db.session.add(sale)
        db.session.commit()
    
    if Expenditure.query.count() == 0:
        import random
        start_date = date(2024, 1, 1)
        end_date = date(2025, 4, 14)
        delta = end_date - start_date
        expenses = ['Seeds', 'Fertilizers', 'Equipment', 'Labor', 'Transport', 'Marketing', 'Utilities', 'Irrigation']
        for i in range(50):
            random_days = random.randint(0, delta.days)
            exp_date = start_date + timedelta(days=random_days)
            amount = round(random.uniform(200, 5000), 2)
            desc = random.choice(expenses)
            exp = Expenditure(amount=amount, date=exp_date, description=desc)
            db.session.add(exp)
        db.session.commit()
    
    if Notification.query.count() == 0:
        notifications = [
            ("New sales lead from Harvest Corp - interested in organic fertilizers", "lead"),
            ("Invoice INV-20240315-102 for $5,200 completed and sent to customer", "invoice"),
            ("Completed sale: Green Farms Ltd - order #AGRO-4521 invoiced", "sale"),
        ]
        for msg, ntype in notifications:
            notif = Notification(message=msg, type=ntype, created_at=datetime.now(timezone.utc) - timedelta(days=random.randint(1,15)))
            db.session.add(notif)
        db.session.commit()
    
    if FollowerData.query.count() == 0:
        import random
        platforms = ['twitter', 'linkedin', 'facebook', 'instagram', 'whatsapp']
        current_year = datetime.now().year
        for year in [current_year-1, current_year]:
            for platform in platforms:
                base = random.randint(500, 5000)
                for month in range(1, 13):
                    count = base + random.randint(-200, 300)
                    if count < 0: count = 0
                    fd = FollowerData(platform=platform, year=year, month=month, count=count)
                    db.session.add(fd)
        db.session.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            abort(403)
        return f(*args, **kwargs)
    return decorated_function

# -------------------------------
# Routes
# -------------------------------

@app.route('/')
def home():
    # If no users exist, go to setup
    if User.query.count() == 0:
        return redirect(url_for('setup'))
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
    # Only allow setup if no users exist
    if User.query.count() > 0:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        if User.query.filter_by(username=username).first():
            return render_template('setup.html', error='Username already taken')
        
        admin = User(username=username, email=email, is_admin=True)
        admin.set_password(password)
        db.session.add(admin)
        db.session.commit()
        return redirect(url_for('login'))
    
    return render_template('setup.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    # If no users exist, redirect to setup
    if User.query.count() == 0:
        return redirect(url_for('setup'))
    
    if request.method == 'POST':
        identifier = request.form['identifier']
        password = request.form['password']
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid email/username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

@app.route('/dashboard')
@login_required
def dashboard():
    return render_template('dashboard.html')

# -------------------------------
# Admin: User Management
# -------------------------------

@app.route('/admin/users')
@admin_required
def admin_users():
    users = User.query.all()
    return render_template('admin_users.html', users=users)

@app.route('/admin/users/add', methods=['POST'])
@admin_required
def admin_add_user():
    username = request.form['username']
    email = request.form['email']
    password = request.form['password']
    is_admin = request.form.get('is_admin') == 'on'
    
    if User.query.filter_by(username=username).first():
        return redirect(url_for('admin_users', error='Username exists'))
    
    new_user = User(username=username, email=email, is_admin=is_admin)
    new_user.set_password(password)
    db.session.add(new_user)
    db.session.commit()
    return redirect(url_for('admin_users'))

@app.route('/admin/users/delete/<int:user_id>')
@admin_required
def admin_delete_user(user_id):
    if user_id == session['user_id']:
        return redirect(url_for('admin_users', error='Cannot delete your own account'))
    user = User.query.get_or_404(user_id)
    db.session.delete(user)
    db.session.commit()
    return redirect(url_for('admin_users'))

# -------------------------------
# Password Recovery Routes
# -------------------------------

@app.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()
        if user:
            token = user.generate_reset_token()
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
# All existing API endpoints (unchanged)
# -------------------------------
# ... (copy them from your previous working app.py)
# To keep this answer readable, I'm not repeating them here.
# But you must keep all your API routes: /api/social_links, /api/sales, etc.
# The above admin additions are the only changes needed.

# For brevity, I list only the new routes. Use your existing API routes as they are.

# -------------------------------
# Create tables and run app (with drop_all to reset schema)
# -------------------------------

with app.app_context():
    db.drop_all()      # Resets schema (remove this after first deploy if you want to keep data)
    db.create_all()
    init_demo_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# For Vercel
app = app
