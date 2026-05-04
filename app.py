import os
from datetime import datetime, timedelta, date
from sqlalchemy import func
from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from flask_sqlalchemy import SQLAlchemy
from flask_bcrypt import Bcrypt
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'verdisol_agro_secret_key_2024'

DATABASE_URL = os.getenv('DATABASE_URL')
if not DATABASE_URL:
    raise Exception("DATABASE_URL environment variable not set")
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL.replace("postgres://", "postgresql://", 1)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)
bcrypt = Bcrypt(app)

# Models
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=True)
    password_hash = db.Column(db.String(128), nullable=False)
    def set_password(self, password):
        self.password_hash = bcrypt.generate_password_hash(password).decode('utf-8')
    def check_password(self, password):
        return bcrypt.check_password_hash(self.password_hash, password)

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
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    is_read = db.Column(db.Boolean, default=False)

class FollowerData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    platform = db.Column(db.String(50), nullable=False)
    year = db.Column(db.Integer, nullable=False)
    month = db.Column(db.Integer, nullable=False)
    count = db.Column(db.Integer, nullable=False, default=0)

# Demo data
def init_demo_data():
    if User.query.count() == 0:
        admin = User(username='admin', email='admin@verdisol.com')
        admin.set_password('admin123')
        db.session.add(admin)
        db.session.commit()
    if SocialLink.query.count() == 0:
        for platform, url, icon in [
            ('twitter', 'https://twitter.com/verdisolagro', 'fab fa-twitter'),
            ('linkedin', 'https://linkedin.com/company/verdisol-agro', 'fab fa-linkedin'),
            ('facebook', 'https://facebook.com/verdisolagro', 'fab fa-facebook'),
            ('instagram', 'https://instagram.com/verdisolagro', 'fab fa-instagram'),
            ('whatsapp', 'https://wa.me/263712345678', 'fab fa-whatsapp')
        ]:
            db.session.add(SocialLink(platform=platform, url=url, icon=icon))
        db.session.commit()
    if Sale.query.count() == 0:
        import random
        start = date(2024,1,1)
        end = date(2025,4,14)
        delta = end - start
        customers = ['John Doe', 'Jane Smith', 'Peter Green', 'Mary Johnson', 'David Brown', 'Susan White']
        titles = ['Mr','Mrs','Miss','Ms']
        services = ['Soil Testing','Crop Advisory','Irrigation Setup','Fertilizer Supply','Drone Survey']
        area_types = ['residential','farm','plot']
        for i in range(40):
            d = start + timedelta(days=random.randint(0, delta.days))
            amount = round(random.uniform(500,15000),2)
            status = 'completed' if (rs:=random.choice(['sent','pending'])) == 'sent' else 'pending'
            sale = Sale(
                customer_title=random.choice(titles),
                customer_name=random.choice(customers),
                service=random.choice(services),
                service_date=d,
                report_status=rs,
                amount=amount,
                area_type=random.choice(area_types),
                area_size=round(random.uniform(0.5,50),1),
                status=status,
                invoice_no=f"INV-{d.strftime('%Y%m%d')}-{i+100}"
            )
            db.session.add(sale)
        db.session.commit()
    if Expenditure.query.count() == 0:
        import random
        start = date(2024,1,1)
        end = date(2025,4,14)
        delta = end - start
        expenses = ['Seeds','Fertilizers','Equipment','Labor','Transport','Marketing','Utilities','Irrigation']
        for i in range(50):
            d = start + timedelta(days=random.randint(0, delta.days))
            db.session.add(Expenditure(amount=round(random.uniform(200,5000),2), date=d, description=random.choice(expenses)))
        db.session.commit()
    if Notification.query.count() == 0:
        for msg,typ in [("New sales lead from Harvest Corp - interested in organic fertilizers","lead"),
                        ("Invoice INV-20240315-102 for $5,200 completed and sent to customer","invoice"),
                        ("Completed sale: Green Farms Ltd - order #AGRO-4521 invoiced","sale")]:
            db.session.add(Notification(message=msg, type=typ, created_at=datetime.utcnow() - timedelta(days=random.randint(1,15))))
        db.session.commit()
    if FollowerData.query.count() == 0:
        import random
        platforms = ['twitter','linkedin','facebook','instagram','whatsapp']
        cur_year = datetime.now().year
        for year in [cur_year-1, cur_year]:
            for platform in platforms:
                base = random.randint(500,5000)
                for month in range(1,13):
                    count = base + random.randint(-200,300)
                    if count < 0: count = 0
                    db.session.add(FollowerData(platform=platform, year=year, month=month, count=count))
        db.session.commit()

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Routes
@app.route('/')
def home():
    return redirect(url_for('login'))

@app.route('/login', methods=['GET','POST'])
def login():
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

# API endpoints (keep all from your original file)
@app.route('/api/social_links', methods=['GET','POST'])
@login_required
def handle_social_links():
    if request.method == 'GET':
        return jsonify([{'platform': l.platform, 'url': l.url, 'icon': l.icon} for l in SocialLink.query.all()])
    else:
        for item in request.json:
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
        'id': s.id, 'customer_title': s.customer_title, 'customer_name': s.customer_name,
        'service': s.service, 'service_date': s.service_date.isoformat(),
        'report_status': s.report_status, 'amount': s.amount, 'area_type': s.area_type,
        'area_size': s.area_size, 'status': s.status, 'invoice_no': s.invoice_no
    } for s in sales])

@app.route('/api/sales', methods=['POST'])
@login_required
def add_sale():
    data = request.json
    last_id = db.session.query(func.max(Sale.id)).scalar() or 0
    invoice_no = f"INV-{datetime.now().strftime('%Y%m%d')}-{last_id+1}"
    status = 'completed' if data['report_status'] == 'sent' else 'pending'
    sale = Sale(
        customer_title=data['customer_title'], customer_name=data['customer_name'],
        service=data['service'], service_date=datetime.strptime(data['service_date'], '%Y-%m-%d').date(),
        report_status=data['report_status'], amount=float(data['amount']),
        area_type=data['area_type'], area_size=float(data['area_size']),
        status=status, invoice_no=invoice_no
    )
    db.session.add(sale)
    db.session.commit()
    db.session.add(Notification(message=f"New sale added: {sale.customer_title} {sale.customer_name} - {sale.service}", type='sale'))
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
        weekly = defaultdict(float)
        for s in sales:
            week = s.service_date.isocalendar()[1]
            key = f"{s.service_date.year}-W{week:02d}"
            weekly[key] += s.amount
        sorted_items = sorted(weekly.items())
        labels = [i[0] for i in sorted_items][-12:]
        values = [i[1] for i in sorted_items][-12:]
    elif period == 'monthly':
        monthly = {}
        for s in sales:
            key = s.service_date.strftime('%Y-%m')
            monthly[key] = monthly.get(key,0) + s.amount
        sorted_items = sorted(monthly.items())
        labels = [i[0] for i in sorted_items][-12:]
        values = [i[1] for i in sorted_items][-12:]
    else:
        quarterly = {}
        for s in sales:
            q = (s.service_date.month-1)//3+1
            key = f"{s.service_date.year}-Q{q}"
            quarterly[key] = quarterly.get(key,0) + s.amount
        sorted_items = sorted(quarterly.items())
        labels = [i[0] for i in sorted_items][-8:]
        values = [i[1] for i in sorted_items][-8:]
    return jsonify({'labels': labels, 'values': values})

@app.route('/api/pending_vs_completed')
@login_required
def pending_vs_completed():
    pending = db.session.query(func.sum(Sale.amount)).filter_by(status='pending').scalar() or 0
    completed = db.session.query(func.sum(Sale.amount)).filter_by(status='completed').scalar() or 0
    return jsonify({'pending': pending, 'completed': completed})

@app.route('/api/income_expenditure')
@login_required
def income_expenditure():
    period = request.args.get('period', 'monthly')
    sales = Sale.query.filter_by(status='completed').all()
    exps = Expenditure.query.all()
    if period == 'monthly':
        inc = {}
        for s in sales:
            k = s.service_date.strftime('%Y-%m')
            inc[k] = inc.get(k,0) + s.amount
        exp = {}
        for e in exps:
            k = e.date.strftime('%Y-%m')
            exp[k] = exp.get(k,0) + e.amount
        dates = sorted(set(inc.keys()) | set(exp.keys()))[-12:]
        return jsonify({'labels': dates, 'income': [inc.get(d,0) for d in dates], 'expenditure': [exp.get(d,0) for d in dates]})
    else:
        inc = {}
        for s in sales:
            q = (s.service_date.month-1)//3+1
            k = f"{s.service_date.year}-Q{q}"
            inc[k] = inc.get(k,0) + s.amount
        exp = {}
        for e in exps:
            q = (e.date.month-1)//3+1
            k = f"{e.date.year}-Q{q}"
            exp[k] = exp.get(k,0) + e.amount
        dates = sorted(set(inc.keys()) | set(exp.keys()))[-8:]
        return jsonify({'labels': dates, 'income': [inc.get(d,0) for d in dates], 'expenditure': [exp.get(d,0) for d in dates]})

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
    n = Notification.query.get(request.json.get('id'))
    if n:
        n.is_read = True
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/add_lead_notification', methods=['POST'])
@login_required
def add_lead_notification():
    customer = request.json.get('customer', 'New Customer')
    db.session.add(Notification(message=f"New sales lead from {customer} - interested in Verdisol products", type='lead'))
    db.session.commit()
    return jsonify({'success': True})

@app.route('/api/sales_summary')
@login_required
def sales_summary():
    total = db.session.query(func.sum(Sale.amount)).scalar() or 0
    pending = db.session.query(func.sum(Sale.amount)).filter_by(status='pending').scalar() or 0
    completed = db.session.query(func.sum(Sale.amount)).filter_by(status='completed').scalar() or 0
    return jsonify({'total_sales': total, 'pending_sales': pending, 'completed_sales': completed})

@app.route('/api/sales_histogram')
@login_required
def sales_histogram():
    amounts = [s.amount for s in Sale.query.all()]
    bins = [0,2000,4000,6000,8000,float('inf')]
    labels = ['$0-2k','$2k-4k','$4k-6k','$6k-8k','$8k+']
    counts = [0]*len(labels)
    for amt in amounts:
        for i,(low,high) in enumerate(zip(bins[:-1], bins[1:])):
            if low <= amt < high:
                counts[i] += 1
                break
    return jsonify({'labels': labels, 'counts': counts})

@app.route('/api/today_sales')
@login_required
def today_sales():
    total = db.session.query(func.sum(Sale.amount)).filter(Sale.service_date == date.today()).scalar() or 0
    return jsonify({'total': total, 'date': date.today().isoformat()})

@app.route('/api/followers', methods=['GET'])
@login_required
def get_followers():
    return jsonify([{'id': d.id, 'platform': d.platform, 'year': d.year, 'month': d.month, 'count': d.count} for d in FollowerData.query.all()])

@app.route('/api/followers', methods=['POST'])
@login_required
def update_followers():
    for item in request.json:
        existing = FollowerData.query.filter_by(platform=item['platform'], year=item['year'], month=item['month']).first()
        if existing:
            existing.count = item['count']
        else:
            db.session.add(FollowerData(platform=item['platform'], year=item['year'], month=item['month'], count=item['count']))
    db.session.commit()
    return jsonify({'success': True})

# Create tables and init data
with app.app_context():
    db.create_all()
    init_demo_data()

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
