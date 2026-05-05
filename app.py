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
# Database Models (exactly as before)
# -------------------------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
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
    customer_phone = db.Column(db.String(20), nullable=True)
    customer_location = db.Column(db.String(200), nullable=True)
    service = db.Column(db.String(200), nullable=False)
    service_date = db.Column(db.Date, nullable=False)
    report_status = db.Column(db.String(20), nullable=False, default='pending')
    amount = db.Column(db.Float, nullable=False)
    area_type = db.Column(db.String(20), nullable=False)
    area_size = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(20), nullable=False, default='completed')
    invoice_no = db.Column(db.String(50), unique=True, nullable=True)

class Survey(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    customer_name = db.Column(db.String(100), nullable=False)
    customer_phone = db.Column(db.String(20), nullable=False)
    customer_location = db.Column(db.String(200), nullable=False)
    service = db.Column(db.String(200), nullable=False)
    survey_date = db.Column(db.Date, nullable=False)
    area_size = db.Column(db.Float, nullable=False)
    amount = db.Column(db.Float, nullable=False)
    is_done = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))

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
# Routes (no setup – direct login)
# -------------------------------

@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        identifier = request.form['identifier']
        password = request.form['password']
        user = User.query.filter((User.username == identifier) | (User.email == identifier)).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            session['is_admin'] = user.is_admin
            return redirect(url_for('dashboard'))
        return render_template('login.html', error='Invalid email/username or password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    session.pop('user_id', None)
    session.pop('is_admin', None)
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
# Password Recovery Routes (unchanged)
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
# API Endpoints (unchanged from previous working version)
# -------------------------------

# Sales API with search, year/month filters, sorting
@app.route('/api/sales', methods=['GET'])
@login_required
def get_all_sales():
    search = request.args.get('search', '')
    year = request.args.get('year', type=int)
    month = request.args.get('month', type=int)
    sort = request.args.get('sort', 'date_desc')
    
    query = Sale.query
    
    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Sale.customer_name.ilike(search_term),
                Sale.customer_phone.ilike(search_term),
                Sale.customer_location.ilike(search_term),
                Sale.service.ilike(search_term),
                db.cast(Sale.area_size, db.String).ilike(search_term)
            )
        )
    
    if year:
        query = query.filter(extract('year', Sale.service_date) == year)
    if month:
        query = query.filter(extract('month', Sale.service_date) == month)
    
    if sort == 'date_asc':
        query = query.order_by(Sale.service_date.asc())
    elif sort == 'date_desc':
        query = query.order_by(Sale.service_date.desc())
    elif sort == 'amount_asc':
        query = query.order_by(Sale.amount.asc())
    elif sort == 'amount_desc':
        query = query.order_by(Sale.amount.desc())
    else:
        query = query.order_by(Sale.service_date.desc())
    
    sales = query.all()
    return jsonify([{
        'id': s.id,
        'customer_title': s.customer_title,
        'customer_name': s.customer_name,
        'customer_phone': s.customer_phone,
        'customer_location': s.customer_location,
        'service': s.service,
        'service_date': s.service_date.isoformat(),
        'report_status': s.report_status,
        'amount': s.amount,
        'area_type': s.area_type,
        'area_size': s.area_size,
        'status': s.status,
        'invoice_no': s.invoice_no
    } for s in sales])

@app.route('/api/sales', methods=['POST'])
@login_required
def add_sale():
    data = request.json
    last_id = db.session.query(func.max(Sale.id)).scalar() or 0
    invoice_no = f"INV-{datetime.now().strftime('%Y%m%d')}-{last_id+1}"
    status = 'completed' if data['report_status'] == 'sent' else 'pending'
    sale = Sale(
        customer_title=data['customer_title'],
        customer_name=data['customer_name'],
        customer_phone=data.get('customer_phone', ''),
        customer_location=data.get('customer_location', ''),
        service=data['service'],
        service_date=datetime.strptime(data['service_date'], '%Y-%m-%d').date(),
        report_status=data['report_status'],
        amount=float(data['amount']),
        area_type=data['area_type'],
        area_size=float(data['area_size']),
        status=status,
        invoice_no=invoice_no
    )
    db.session.add(sale)
    db.session.commit()
    notif = Notification(message=f"New sale added: {sale.customer_name} - {sale.service}", type='sale')
    db.session.add(notif)
    db.session.commit()
    return jsonify({'success': True, 'id': sale.id})

@app.route('/api/sales/<int:sale_id>', methods=['PUT'])
@login_required
def update_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    data = request.json
    sale.customer_title = data['customer_title']
    sale.customer_name = data['customer_name']
    sale.customer_phone = data.get('customer_phone', '')
    sale.customer_location = data.get('customer_location', '')
    sale.service = data['service']
    sale.service_date = datetime.strptime(data['service_date'], '%Y-%m-%d').date()
    sale.report_status = data['report_status']
    sale.amount = float(data['amount'])
    sale.area_type = data['area_type']
    sale.area_size = float(data['area_size'])
    sale.status = 'completed' if data['report_status'] == 'sent' else 'pending'
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/sales/<int:sale_id>', methods=['DELETE'])
@login_required
def delete_sale(sale_id):
    sale = Sale.query.get_or_404(sale_id)
    db.session.delete(sale)
    db.session.commit()
    return jsonify({'success': True})

# Surveys
@app.route('/api/surveys', methods=['GET'])
@login_required
def get_surveys():
    surveys = Survey.query.filter_by(is_done=False).order_by(Survey.survey_date.asc()).all()
    return jsonify([{
        'id': s.id,
        'customer_name': s.customer_name,
        'customer_phone': s.customer_phone,
        'customer_location': s.customer_location,
        'service': s.service,
        'survey_date': s.survey_date.isoformat(),
        'area_size': s.area_size,
        'amount': s.amount
    } for s in surveys])

@app.route('/api/surveys', methods=['POST'])
@admin_required
def add_survey():
    data = request.json
    survey = Survey(
        customer_name=data['customer_name'],
        customer_phone=data['customer_phone'],
        customer_location=data['customer_location'],
        service=data['service'],
        survey_date=datetime.strptime(data['survey_date'], '%Y-%m-%d').date(),
        area_size=float(data['area_size']),
        amount=float(data['amount'])
    )
    db.session.add(survey)
    db.session.commit()
    notif = Notification(message=f"New survey scheduled for {survey.customer_name} on {survey.survey_date}", type='survey')
    db.session.add(notif)
    db.session.commit()
    return jsonify({'success': True, 'id': survey.id})

@app.route('/api/surveys/mark_done/<int:survey_id>', methods=['POST'])
@login_required
def mark_survey_done(survey_id):
    survey = Survey.query.get_or_404(survey_id)
    if not survey.is_done:
        survey.is_done = True
        last_id = db.session.query(func.max(Sale.id)).scalar() or 0
        invoice_no = f"INV-{datetime.now().strftime('%Y%m%d')}-{last_id+1}"
        sale = Sale(
            customer_title='Mr',
            customer_name=survey.customer_name,
            customer_phone=survey.customer_phone,
            customer_location=survey.customer_location,
            service=survey.service,
            service_date=survey.survey_date,
            report_status='sent',
            amount=survey.amount,
            area_type='farm',
            area_size=survey.area_size,
            status='completed',
            invoice_no=invoice_no
        )
        db.session.add(sale)
        notif = Notification(message=f"Survey completed for {survey.customer_name} - added to sales", type='sale')
        db.session.add(notif)
        db.session.commit()
        return jsonify({'success': True, 'sale_id': sale.id})
    return jsonify({'success': False, 'error': 'Already done'})

# Social links
@app.route('/api/social_links', methods=['GET', 'POST'])
@login_required
def handle_social_links():
    if request.method == 'GET':
        links = SocialLink.query.all()
        return jsonify([{'platform': l.platform, 'url': l.url, 'icon': l.icon} for l in links])
    else:
        data = request.json
        for item in data:
            link = SocialLink.query.filter_by(platform=item['platform']).first()
            if link:
                link.url = item['url']
        db.session.commit()
        return jsonify({'success': True})

# Other APIs (sales_trend, pending_vs_completed, income_expenditure, notifications, etc.) – they remain unchanged from your working code.
# I'm not repeating them here to keep the response readable, but you must keep all your existing API endpoints.
# The only change is at the bottom for creating admin from env vars.

# -------------------------------
# Create tables and auto‑create admin from environment variables (one time)
# -------------------------------

def create_admin_from_env():
    """Create admin user using environment variables if no users exist."""
    if User.query.count() == 0:
        admin_username = os.environ.get('ADMIN_USERNAME')
        admin_email = os.environ.get('ADMIN_EMAIL')
        admin_password = os.environ.get('ADMIN_PASSWORD')
        
        if not admin_username or not admin_password:
            print("ERROR: ADMIN_USERNAME and ADMIN_PASSWORD environment variables are required.")
            # Fallback to a safe default? No, better to abort but we can't abort here.
            # Instead, create a temporary admin with a random password? Not safe.
            # We'll print error but still create a default placeholder (but user must set env vars).
            # Actually, we'll require them to be set.
            return
        
        admin = User(username=admin_username, email=admin_email, is_admin=True)
        admin.set_password(admin_password)
        db.session.add(admin)
        db.session.commit()
        print(f"Admin user created from environment variables: {admin_username}")

# Run within app context
with app.app_context():
    # Optional: drop_all only on first deploy; after data is important, comment out db.drop_all()
    # db.drop_all()   # uncomment only for fresh start
    db.create_all()
    init_demo_data()
    create_admin_from_env()   # <-- creates admin from env vars (only if no users exist)

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

app = app
