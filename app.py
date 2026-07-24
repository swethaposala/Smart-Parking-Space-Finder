from flask import Flask, render_template, request, redirect, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timedelta
import re

app = Flask(__name__)
app.secret_key = "smartparking"

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///parking.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db = SQLAlchemy(app)

# ---------------- DATABASE MODELS ----------------

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(100))
    password = db.Column(db.String(100))
    role = db.Column(db.String(20))


class Slot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    owner = db.Column(db.String(100))
    slot_number = db.Column(db.Integer)
    location = db.Column(db.String(200))

    car_price = db.Column(db.Integer)
    bike_price = db.Column(db.Integer)

    facilities = db.Column(db.String(200))
    status = db.Column(db.String(20), default="Available")


class Booking(db.Model):
    id = db.Column(db.Integer, primary_key=True)

    username = db.Column(db.String(100))
    vehicle = db.Column(db.String(50))
    vehicle_type = db.Column(db.String(50))

    slot_number = db.Column(db.Integer)

    start_time = db.Column(db.String(100))
    end_time = db.Column(db.String(100))

    hours = db.Column(db.Integer)
    amount = db.Column(db.Integer)


# ---------------- LOGIN ----------------

@app.route("/", methods=["GET", "POST"])
def login():

    if request.method == "POST":

        username = request.form['username']
        password = request.form['password']

        user = User.query.filter_by(username=username, password=password).first()

        if user:

            session['user'] = username
            session['role'] = user.role

            if user.role == "owner":
                return redirect("/owner_dashboard")
            else:
                return redirect("/user_dashboard")

    return render_template("login.html")


# ---------------- REGISTER ----------------

@app.route("/register", methods=["GET", "POST"])
def register():

    if request.method == "POST":

        username = request.form['username']
        password = request.form['password']
        role = request.form['role']

        new_user = User(username=username, password=password, role=role)

        db.session.add(new_user)
        db.session.commit()

        return redirect("/")

    return render_template("register.html")


# ---------------- LOGOUT ----------------

@app.route("/logout")
def logout():

    session.clear()
    return redirect("/")


# ---------------- USER DASHBOARD ----------------

@app.route("/user_dashboard")
def user_dashboard():

    if 'user' not in session or session.get("role") != "user":
        return redirect("/")

    location = request.args.get("location")
    facility = request.args.get("facility")

    slots = Slot.query.filter_by(status="Available")

    if location:
        slots = slots.filter(Slot.location.ilike(f"%{location}%"))

    if facility:
        slots = slots.filter(Slot.facilities.ilike(f"%{facility}%"))

    slots = slots.all()

    return render_template("user_dashboard.html", slots=slots)


# ---------------- BOOK SLOT ----------------

@app.route("/book/<int:id>", methods=["POST"])
def book(id):

    if 'user' not in session:
        return redirect("/")

    slot = Slot.query.get(id)

    vehicle = request.form['vehicle'].upper()
    vehicle_type = request.form['vehicle_type']
    hours = int(request.form['hours'])

    # Vehicle number validation
    pattern = r"^[A-Z]{2}[0-9]{2}[A-Z]{2}[0-9]{4}$"

    if not re.match(pattern, vehicle):
        return "Invalid Vehicle Number Format"

    # Price calculation
    if vehicle_type == "Car":
        price = slot.car_price

    elif vehicle_type == "Bike":
        price = slot.bike_price

    start_time = datetime.now()
    end_time = start_time + timedelta(hours=hours)

    amount = price * hours

    session['booking_data'] = {

        "vehicle": vehicle,
        "vehicle_type": vehicle_type,
        "slot": slot.slot_number,
        "hours": hours,
        "start": start_time.strftime("%Y-%m-%d %H:%M"),
        "end": end_time.strftime("%Y-%m-%d %H:%M"),
        "amount": amount

    }

    return redirect("/reservation")


# ---------------- RESERVATION PAGE ----------------

@app.route("/reservation")
def reservation():

    if 'booking_data' not in session:
        return redirect("/user_dashboard")

    return render_template("reservation.html", data=session['booking_data'])


# ---------------- CONFIRM PAYMENT ----------------

@app.route("/confirm_payment")
def confirm_payment():

    data = session['booking_data']

    booking = Booking(

        username=session['user'],
        vehicle=data['vehicle'],
        vehicle_type=data['vehicle_type'],
        slot_number=data['slot'],
        start_time=data['start'],
        end_time=data['end'],
        hours=data['hours'],
        amount=data['amount']

    )

    slot = Slot.query.filter_by(slot_number=data['slot']).first()

    slot.status = "Reserved"

    db.session.add(booking)
    db.session.commit()

    session.pop('booking_data', None)

    return redirect("/user_dashboard")


# ---------------- USER BOOKING HISTORY ----------------

@app.route("/user_history")
def user_history():

    if 'user' not in session:
        return redirect("/")

    bookings = Booking.query.filter_by(username=session['user']).all()

    return render_template("user_history.html", bookings=bookings)


# ---------------- OWNER DASHBOARD ----------------

@app.route("/owner_dashboard")
def owner_dashboard():

    if 'user' not in session or session.get("role") != "owner":
        return redirect("/")

    slots = Slot.query.filter_by(owner=session['user']).all()

    return render_template("owner_dashboard.html", slots=slots)


# ---------------- ADD SLOT ----------------

@app.route("/add_slot", methods=["GET", "POST"])
def add_slot():

    if 'user' not in session or session.get("role") != "owner":
        return redirect("/")

    if request.method == "POST":

        total_slots = int(request.form['total_slots'])

        location = request.form['location']

        car_price = request.form['car_price']
        bike_price = request.form['bike_price']

        facilities = request.form.getlist("facilities")
        facilities = ", ".join(facilities)

        for i in range(total_slots):

            slot = Slot(

                owner=session['user'],
                slot_number=i + 1,
                location=location,

                car_price=car_price,
                bike_price=bike_price,

                facilities=facilities

            )

            db.session.add(slot)

        db.session.commit()

        return redirect("/owner_dashboard")

    return render_template("add_slot.html")


# ---------------- OWNER BOOKING HISTORY ----------------

@app.route("/owner_history")
def owner_history():

    if 'user' not in session:
        return redirect("/")

    slots = Slot.query.filter_by(owner=session['user']).all()

    slot_numbers = [s.slot_number for s in slots]

    bookings = Booking.query.filter(Booking.slot_number.in_(slot_numbers)).all()

    return render_template("owner_history.html", bookings=bookings)


# ---------------- RUN APP ----------------

if __name__ == "__main__":

    with app.app_context():
        db.create_all()

    app.run(debug=True)