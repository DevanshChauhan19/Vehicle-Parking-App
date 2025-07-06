# app/routes/auth.py
from flask import render_template, request, redirect, session, url_for, Flask
from werkzeug.security import generate_password_hash, check_password_hash
from models import db, User, ParkingLot,ParkingSpot,Reservation
import os
from datetime import datetime

# Initialize the app and configure the database
app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking_app.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = os.urandom(24)

db.init_app(app)

@app.route("/")
def home():
    return redirect(url_for("login"))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        name = request.form['name']
        address=request.form['address']
        pincode=request.form['pincode']

        if User.query.filter_by(email=email).first():
            return 'Email already registered.'

        if not email or not password or not name or not address or not pincode:
            return 'All fields are required.'

        if len(password) < 6:
            return 'Password must be at least 6 characters.'

        if not pincode.isdigit() or len(pincode) != 6:
            return 'Invalid pincode.'

        hashed_pw = generate_password_hash(password)
        new_user = User(name=name, email=email, password_hash=hashed_pw,address=address,pincode=pincode)
        db.session.add(new_user)
        db.session.commit()
        return redirect(url_for('login'))

    return render_template('register.html', page='register')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        email = request.form['email']
        password = request.form['password']
        user = User.query.filter_by(email=email).first()
        if user and check_password_hash(user.password_hash, password):
            if user.is_admin:
                session['user'] = 'admin'
                return redirect(url_for('admin_dashboard'))
            else:
                session['user'] = user.id
                return redirect(url_for('user_dashboard'))

        return 'Invalid credentials.'

    return render_template('login.html', page='login')


@app.route('/admin/dashboard')
def admin_dashboard():
    if session.get('user') != 'admin':
        return redirect(url_for('login'))

    query = request.args.get('query', '')
    if query:
        lots = ParkingLot.query.filter(
            (ParkingLot.name.ilike(f"%{query}%")) |
            (ParkingLot.pin_code.ilike(f"%{query}%"))
        ).all()
    else:
        lots = ParkingLot.query.all()
    
    # Chart Data: Reservations per lot
    labels = []
    data = []
    for lot in lots:
        count = sum(len(spot.reservations) for spot in lot.spots)
        labels.append(lot.name)
        data.append(count)
    
    # Count available and occupied spots
    available_spots = sum(
        1 for lot in lots for spot in lot.spots if spot.status == 'A'
    )
    occupied_spots = sum(
        1 for lot in lots for spot in lot.spots if spot.status == 'O'
    )

    # Reservation count per user
    user_data = (
        db.session.query(User.name, db.func.count(Reservation.id))
        .join(Reservation)
        .filter(User.is_admin == False)
        .group_by(User.name)
        .all()
    )

    user_labels = [u[0] for u in user_data]
    user_counts = [u[1] for u in user_data]

    return render_template('admin_dashboard.html', lots=lots,query=query,chart_labels=labels,chart_data=data,available_spots=available_spots,occupied_spots=occupied_spots,user_labels=user_labels,user_counts=user_counts)

@app.route('/admin/users')
def admin_users():
    if session.get('user') != 'admin':
        return redirect(url_for('login'))

    query = request.args.get('query', '')
    if query:
        users = User.query.filter(
            User.is_admin == False,
            (User.name.ilike(f"%{query}%")) |
            (User.email.ilike(f"%{query}%"))
        ).all()
    else:
        users = User.query.filter_by(is_admin=False).all()
        
    return render_template('admin_users.html', users=users, query=query)

@app.route('/admin/reservations')
def admin_reservations():
    if session.get('user') != 'admin':
        return redirect(url_for('login'))

    filter_status = request.args.get('status', 'all')

    if filter_status == 'active':
        reservations = Reservation.query.filter_by(release_time=None).order_by(Reservation.parking_time.desc()).all()
    elif filter_status == 'completed':
        reservations = Reservation.query.filter(Reservation.release_time.isnot(None)).order_by(Reservation.parking_time.desc()).all()
    else:
        reservations = Reservation.query.order_by(Reservation.parking_time.desc()).all()

    return render_template('admin_reservations.html', reservations=reservations, filter_status=filter_status)

@app.route('/admin/add_lot', methods=['GET', 'POST'])
def add_lot():
    if session.get('user') != 'admin':
        return redirect(url_for('login'))

    if request.method == 'POST':
        name = request.form['name']
        address = request.form['address']
        pin_code = request.form['pin_code']
        price = float(request.form['price'])
        max_spots = int(request.form['max_spots'])

        lot = ParkingLot(name=name, address=address, pin_code=pin_code,
                         price=price, max_spots=max_spots)
        db.session.add(lot)
        db.session.commit()

        # Auto-generate parking spots
        for _ in range(max_spots):
            spot = ParkingSpot(lot_id=lot.id, status='A')
            db.session.add(spot)
        db.session.commit()

        return redirect(url_for('admin_dashboard'))

    return render_template('add_lot.html')

@app.route('/admin/lot/<int:lot_id>/spots')
def view_lot_spots(lot_id):
    if session.get('user') != 'admin':
        return redirect(url_for('login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    return render_template('admin_lot_spots.html', lot=lot)

@app.route('/admin/delete_spot/<int:spot_id>')
def delete_spot(spot_id):
    if session.get('user') != 'admin':
        return redirect(url_for('login'))

    spot = ParkingSpot.query.get_or_404(spot_id)

    if spot.status == 'A':
        db.session.delete(spot)
        db.session.commit()

    return redirect(url_for('view_lot_spots', lot_id=spot.lot_id))


@app.route('/admin/delete_lot/<int:lot_id>')
def delete_lot(lot_id):
    if session.get('user') != 'admin':
        return redirect(url_for('login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    if all(spot.status == 'A' for spot in lot.spots):
        for spot in lot.spots:
            db.session.delete(spot)
        db.session.delete(lot)
        db.session.commit()

    return redirect(url_for('admin_dashboard'))

@app.route('/user/dashboard')
def user_dashboard():
    user_id = session.get('user')
    if not isinstance(user_id, int):
        return redirect(url_for('login'))

    lots = ParkingLot.query.all()

    active_res = Reservation.query.filter_by(user_id=user_id, release_time=None).first()
    history = Reservation.query.filter(Reservation.user_id == user_id, Reservation.release_time != None).all()

    return render_template('user_dashboard.html', lots=lots, active_res=active_res, history=history)


@app.route('/user/reserve/<int:lot_id>', methods=['GET', 'POST'])
def reserve_spot(lot_id):
    user_id = session.get('user')
    if not isinstance(user_id, int):
        return redirect(url_for('login'))

    lot = ParkingLot.query.get_or_404(lot_id)
    available_spots = ParkingSpot.query.filter_by(lot_id=lot.id, status='A').all()

    # Check if user already has an active reservation
    existing = Reservation.query.filter_by(user_id=user_id, release_time=None).first()
    if existing:
        return "You already have an active reservation."

    if request.method == 'POST':
        spot_id = int(request.form['spot_id'])
        spot = ParkingSpot.query.get_or_404(spot_id)

        # Final check that spot is still available
        if spot.status != 'A':
            return "Selected spot is no longer available."

        spot.status = 'O'
        new_res = Reservation(
            user_id=user_id,
            spot_id=spot.id,
            parking_time=datetime.now()
        )
        db.session.add(new_res)
        db.session.commit()
        return redirect(url_for('user_dashboard'))

    return render_template('reserve_spot.html', lot=lot, spots=available_spots)


@app.route('/user/release/<int:reservation_id>')
def release_spot(reservation_id):
    reservation = Reservation.query.get_or_404(reservation_id)
    if reservation.release_time is not None:
        return "Spot already released."

    reservation.release_time = datetime.now()

    # Calculate cost
    lot_price = reservation.spot.lot.price
    duration_hours = (reservation.release_time - reservation.parking_time).total_seconds() / 3600
    reservation.cost = round(duration_hours * lot_price, 2)

    reservation.spot.status = 'A'
    db.session.commit()

    return redirect(url_for('user_dashboard'))


@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect(url_for('login'))

if __name__ == '__main__':
    with app.app_context():
        db.create_all()
    app.run()