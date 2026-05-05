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
    if User.query.count() == 0:
        return redirect(url_for('setup'))
    return redirect(url_for('login'))

@app.route('/setup', methods=['GET', 'POST'])
def setup():
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
    if User.query.count() == 0:
        return redirect(url_for('setup'))
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
# TEMPORARY FIX: Make first user admin (visit /make-me-admin once)
# Remove this route after you see "is now admin"
# -------------------------------
@app.route('/make-me-admin')
def make_me_admin():
    # Only works if there is at least one user and no admin exists yet
    admin_exists = User.query.filter_by(is_admin=True).first()
    if admin_exists:
        return "An admin already exists. This route is no longer needed."
    user = User.query.first()
    if user:
        user.is_admin = True
        db.session.commit()
        # Update session if currently logged in
        if 'user_id' in session and session['user_id'] == user.id:
            session['is_admin'] = True
        return f"✅ User '{user.username}' is now admin. <a href='/admin/users'>Go to Admin Panel</a>"
    return "No user found. Please create an account via /setup first."

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
# Password Recovery
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
# API Endpoints (all your existing ones)
# -------------------------------

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

@app.route('/api/sales', methods=['GET'])
@login_required
def get_all_sales():
    sales = Sale.query.order_by(Sale.service_date.desc()).all()
    return jsonify([{
        'id': s.id,
        'customer_title': s.customer_title,
        'customer_name': s.customer_name,
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
    notif = Notification(message=f"New sale added: {sale.customer_title} {sale.customer_name} - {sale.service}", type='sale')
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

@app.route('/api/sales_trend')
@login_required
def sales_trend():
    period = request.args.get('period', 'monthly')
    status = request.args.get('status', 'all')
    query = Sale.query
    if status != 'all':
        query = query.filter_by(status=status)
    sales = query.all()
    
    if period == 'weekly':
        from collections import defaultdict
        weekly_data = defaultdict(float)
        for sale in sales:
            week_num = sale.service_date.isocalendar()[1]
            year = sale.service_date.year
            key = f"{year}-W{week_num:02d}"
            weekly_data[key] += sale.amount
        sorted_items = sorted(weekly_data.items(), key=lambda x: x[0])
        labels = [item[0] for item in sorted_items][-12:]
        values = [item[1] for item in sorted_items][-12:]
    elif period == 'monthly':
        monthly_data = {}
        for sale in sales:
            key = sale.service_date.strftime('%Y-%m')
            monthly_data[key] = monthly_data.get(key, 0) + sale.amount
        sorted_items = sorted(monthly_data.items())
        labels = [item[0] for item in sorted_items][-12:]
        values = [item[1] for item in sorted_items][-12:]
    else:
        quarterly_data = {}
        for sale in sales:
            quarter = (sale.service_date.month - 1) // 3 + 1
            key = f"{sale.service_date.year}-Q{quarter}"
            quarterly_data[key] = quarterly_data.get(key, 0) + sale.amount
        sorted_items = sorted(quarterly_data.items())
        labels = [item[0] for item in sorted_items][-8:]
        values = [item[1] for item in sorted_items][-8:]
    return jsonify({'labels': labels, 'values': values})

@app.route('/api/pending_vs_completed')
@login_required
def pending_vs_completed():
    pending_total = db.session.query(func.sum(Sale.amount)).filter_by(status='pending').scalar() or 0
    completed_total = db.session.query(func.sum(Sale.amount)).filter_by(status='completed').scalar() or 0
    return jsonify({'pending': pending_total, 'completed': completed_total})

@app.route('/api/income_expenditure')
@login_required
def income_expenditure():
    period = request.args.get('period', 'monthly')
    sales = Sale.query.filter_by(status='completed').all()
    expenditures = Expenditure.query.all()
    if period == 'monthly':
        income_data = {}
        for sale in sales:
            key = sale.service_date.strftime('%Y-%m')
            income_data[key] = income_data.get(key, 0) + sale.amount
        expense_data = {}
        for exp in expenditures:
            key = exp.date.strftime('%Y-%m')
            expense_data[key] = expense_data.get(key, 0) + exp.amount
        all_dates = sorted(set(list(income_data.keys()) + list(expense_data.keys())))[-12:]
        income_values = [income_data.get(d, 0) for d in all_dates]
        expense_values = [expense_data.get(d, 0) for d in all_dates]
        return jsonify({'labels': all_dates, 'income': income_values, 'expenditure': expense_values})
    else:
        income_quarter = {}
        for sale in sales:
            quarter = (sale.service_date.month - 1) // 3 + 1
            key = f"{sale.service_date.year}-Q{quarter}"
            income_quarter[key] = income_quarter.get(key, 0) + sale.amount
        expense_quarter = {}
        for exp in expenditures:
            quarter = (exp.date.month - 1) // 3 + 1
            key = f"{exp.date.year}-Q{quarter}"
            expense_quarter[key] = expense_quarter.get(key, 0) + exp.amount
        all_quarters = sorted(set(list(income_quarter.keys()) + list(expense_quarter.keys())))[-8:]
        income_values = [income_quarter.get(q, 0) for q in all_quarters]
        expense_values = [expense_quarter.get(q, 0) for q in all_quarters]
        return jsonify({'labels': all_quarters, 'income': income_values, 'expenditure': expense_values})

@app.route('/api/notifications')
@login_required
def get_notifications():
    notifs = Notification.query.order_by(Notification.created_at.desc()).limit(20).all()
    return jsonify([{
        'id': n.id, 'message': n.message, 'type': n.type,
        'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'), 'is_read': n.is_read
    } for n in notifs])

@app.route('/api/notifications/mark_read', methods=['POST'])
@login_required
def mark_notification_read():
    data = request.json
    notif = Notification.query.get(data.get('id'))
    if notif:
        notif.is_read = True
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/add_lead_notification', methods=['POST'])
@login_required
def add_lead_notification():
    data = request.json
    customer = data.get('customer', 'New Customer')
    message = f"New sales lead from {customer} - interested in Verdisol products"
    notif = Notification(message=message, type='lead')
    db.session.add(notif)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/sales_summary')
@login_required
def sales_summary():
    total_sales = db.session.query(func.sum(Sale.amount)).scalar() or 0
    pending_total = db.session.query(func.sum(Sale.amount)).filter_by(status='pending').scalar() or 0
    completed_total = db.session.query(func.sum(Sale.amount)).filter_by(status='completed').scalar() or 0
    return jsonify({'total_sales': total_sales, 'pending_sales': pending_total, 'completed_sales': completed_total})

@app.route('/api/sales_histogram')
@login_required
def sales_histogram():
    sales = Sale.query.all()
    amounts = [s.amount for s in sales]
    bins = [0, 2000, 4000, 6000, 8000, float('inf')]
    labels = ['$0-2k', '$2k-4k', '$4k-6k', '$6k-8k', '$8k+']
    counts = [0]*len(labels)
    for amt in amounts:
        for i, (low, high) in enumerate(zip(bins[:-1], bins[1:])):
            if low <= amt < high:
                counts[i] += 1
                break
    return jsonify({'labels': labels, 'counts': counts})

@app.route('/api/today_sales')
@login_required
def today_sales():
    today = date.today()
    total = db.session.query(func.sum(Sale.amount)).filter(Sale.service_date == today).scalar() or 0
    return jsonify({'total': total, 'date': today.isoformat()})

@app.route('/api/followers', methods=['GET'])
@login_required
def get_followers():
    data = FollowerData.query.all()
    return jsonify([{
        'id': d.id,
        'platform': d.platform,
        'year': d.year,
        'month': d.month,
        'count': d.count
    } for d in data])

@app.route('/api/followers', methods=['POST'])
@login_required
def update_followers():
    data = request.json
    for item in data:
        existing = FollowerData.query.filter_by(
            platform=item['platform'],
            year=item['year'],
            month=item['month']
        ).first()
        if existing:
            existing.count = item['count']
        else:
            new_entry = FollowerData(
                platform=item['platform'],
                year=item['year'],
                month=item['month'],
                count=item['count']
            )
            db.session.add(new_entry)
    db.session.commit()
    return jsonify({'success': True})

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
# Create tables and run app
# -------------------------------

with app.app_context():
    db.drop_all()
    db.create_all()
    init_demo_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)

# For Vercel
app = app
