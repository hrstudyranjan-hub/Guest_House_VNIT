from flask import Flask, render_template, redirect, request, url_for, session, flash
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime

app = Flask(__name__)

# ---------- Configuration ----------
app.config['SQLALCHEMY_DATABASE_URI'] = "sqlite:///vnit_guest_house.db"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'vnit_secret_key_2025' 

db = SQLAlchemy(app)

# ---------- Database Models ----------

class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.String(6), unique=True, nullable=False)   
    enrollment_no = db.Column(db.String(20), unique=True, nullable=False) 
    password = db.Column(db.String(100), nullable=False)
    name = db.Column(db.String(100), nullable=False)
    gender = db.Column(db.String(10), nullable=False) 
    email = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(15), nullable=False)

class GuestHouse(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    restriction = db.Column(db.String(20), default="None") 
    rooms = db.relationship('RoomInventory', backref='house', lazy=True)

class RoomInventory(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    house_id = db.Column(db.Integer, db.ForeignKey('guest_house.id'), nullable=False)
    room_type = db.Column(db.String(50), nullable=False)
    price = db.Column(db.Integer, nullable=False)
    available_count = db.Column(db.Integer, nullable=False)

# ---------- Database Initialization ----------
with app.app_context():
    db.create_all()

    # Pre-populating Test Student
    if not Student.query.filter_by(student_id="123456").first():
        db.session.add(Student(
            student_id="123456", enrollment_no="BT21CME007",
            password="password123", name="Cristiano Ronaldo", 
            gender="Male", email="CR7@vnit.ac.in", phone="9856543210"
        ))
    
    # Pre-populating Guest Houses and Room Distribution
    if not GuestHouse.query.first():
        h1 = GuestHouse(id=1, name="Dr. Anandi Gopal Guest House", restriction="Women Only")
        h2 = GuestHouse(id=2, name="Common Guest House", restriction="None")
        h3 = GuestHouse(id=3, name="S. Ramanujan Guest House", restriction="None")
        db.session.add_all([h1, h2, h3])
        
        room_types = [
            {'type': 'Single AC', 'price': 1200, 'count': 5},
            {'type': 'Single Non-AC', 'price': 800, 'count': 10},
            {'type': 'Shared AC', 'price': 600, 'count': 8},
            {'type': 'Shared Non-AC', 'price': 400, 'count': 15}
        ]
        
        for house in [h1, h2, h3]:
            for r in room_types:
                db.session.add(RoomInventory(house_id=house.id, room_type=r['type'], price=r['price'], available_count=r['count']))
        
        db.session.commit()

# ---------- Routes ----------

@app.route('/')
def home_page():
    return render_template('start.html')

@app.route('/about-us')
def about_us():
    return render_template('about_us.html')

@app.route('/official')
def official_page():
    return render_template('official.html')

@app.route('/verify-student', methods=['GET', 'POST'])
def student_verification():
    if request.method == 'POST':
        user_id = request.form.get('id')
        user_pass = request.form.get('password')
        student = Student.query.filter_by(student_id=user_id).first()

        if student and student.password == user_pass:
            session['user_id'] = student.student_id
            session['user_name'] = student.name
            session['user_enrollment'] = student.enrollment_no
            session['user_phone'] = student.phone
            return redirect(url_for('guest_house_selection'))
        
        flash("Invalid Credentials", "danger")
    return render_template('student_verification.html')

@app.route('/guest-houses')
def guest_house_selection():
    if 'user_id' not in session: return redirect(url_for('student_verification'))
    houses = GuestHouse.query.all()
    
    # Logic: Check if EVERY room in EVERY house is sold out
    all_full = True
    for house in houses:
        for room in house.rooms:
            if room.available_count > 0:
                all_full = False
                break
    
    return render_template('guest_house.html', houses=houses, all_full=all_full)

@app.route('/booking/<int:house_id>')
def booking_page(house_id):
    if 'user_id' not in session: return redirect(url_for('student_verification'))
    house = GuestHouse.query.get_or_404(house_id)
    return render_template('students.html', house=house)

@app.route('/confirm-booking', methods=['POST'])
def confirm_booking():
    if 'user_id' not in session: return redirect(url_for('student_verification'))

    house_id = int(request.form.get('house_id'))
    guest_gender = request.form.get('guest_gender')
    room_type = request.form.get('room_type')
    arrival_str = request.form.get('arrival')
    departure_str = request.form.get('departure')
    
    # Validation
    if house_id == 1 and guest_gender != "Female":
        flash("Restriction Error: Only Female guests allowed in Anandi Gopal.", "danger")
        return redirect(url_for('guest_house_selection'))

    arrival = datetime.strptime(arrival_str, '%Y-%m-%d')
    departure = datetime.strptime(departure_str, '%Y-%m-%d')
    days = (departure - arrival).days
    if days <= 0: days = 1

    room_record = RoomInventory.query.filter_by(house_id=house_id, room_type=room_type).first()
    
    if not room_record or room_record.available_count <= 0:
        flash(f"Sorry, {room_type} is full!", "danger")
        return redirect(url_for('guest_house_selection'))

    # Money Logic
    base_price = room_record.price * days
    gst = base_price * 0.12
    service_charge = 50.0
    total_amount = base_price + gst + service_charge

    session['pending_booking'] = {
        'house_id': house_id,
        'house_name': GuestHouse.query.get(house_id).name,
        'room_type': room_type,
        'guest_name': request.form.get('guest_name'),
        'base_price': base_price,
        'gst': gst,
        'service_charge': service_charge,
        'total_amount': total_amount,
        'days': days,
        'arrival': arrival_str,
        'departure': departure_str
    }
    return redirect(url_for('payment_page'))

@app.route('/payment')
def payment_page():
    data = session.get('pending_booking')
    if not data: return redirect(url_for('guest_house_selection'))
    return render_template('payment.html', data=data)

@app.route('/process-payment', methods=['POST'])
def process_payment():
    data = session.get('pending_booking')
    if not data: return redirect(url_for('home_page'))

    room_record = RoomInventory.query.filter_by(
        house_id=data['house_id'], 
        room_type=data['room_type']
    ).first()

    if room_record.available_count > 0:
        room_record.available_count -= 1
        db.session.commit()
        session.pop('pending_booking', None)
        return render_template('payment_success.html')
    
    flash("Room sold out during transaction!", "danger")
    return redirect(url_for('guest_house_selection'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('home_page'))

if __name__ == "__main__":

    app.run(host="0.0.0.0", port=10000)
