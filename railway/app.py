from flask import Flask, request, redirect, session, render_template
from datetime import datetime
from functools import wraps
import re

app = Flask(__name__)
app.secret_key = "replace-with-a-random-secret-key"

# In-memory data: all data resets when the app stops.
users = []
bookings = []
# Sample seed data for the college project: 100 Indian cities and 120 demo routes.
# These train numbers, names, distances and routes are generated for demonstration;
# they are NOT official Indian Railways schedules or live train data.
CITIES = [
    "Agra", "Ahmedabad", "Ajmer", "Akola", "Alappuzha", "Allahabad", "Amravati", "Amritsar", "Anand",
    "Anantapur", "Aurangabad", "Bengaluru", "Berhampur", "Bhopal", "Bhubaneswar", "Bidar", "Bilaspur",
    "Chandigarh", "Chennai", "Chittoor", "Coimbatore", "Cuddalore", "Cuttack", "Darbhanga", "Dehradun",
    "Delhi", "Dhanbad", "Dharwad", "Dindigul", "Durgapur", "Eluru", "Erode", "Gandhinagar", "Gaya",
    "Guntur", "Gurugram", "Guwahati", "Gwalior", "Howrah", "Hubballi", "Hyderabad", "Indore", "Jabalpur",
    "Jaipur", "Jalandhar", "Jalgaon", "Jammu", "Jamnagar", "Jamshedpur", "Jhansi", "Jodhpur", "Kadapa",
    "Kakinada", "Kannur", "Kanpur", "Karimnagar", "Kochi", "Kohima", "Kolhapur", "Kolkata", "Kollam",
    "Kota", "Kozhikode", "Kurnool", "Lucknow", "Ludhiana", "Madurai", "Mangaluru", "Meerut", "Mumbai",
    "Mysuru", "Nagpur", "Nanded", "Nashik", "Nellore", "Nizamabad", "Ongole", "Palakkad", "Panaji",
    "Patna", "Pondicherry", "Prayagraj", "Pune", "Raipur", "Rajahmundry", "Rajkot", "Ranchi", "Rourkela",
    "Salem", "Sangli", "Satara", "Shimla", "Siliguri", "Solapur", "Surat", "Tirupati", "Tiruchirappalli",
    "Tirunelveli", "Thiruvananthapuram", "Udaipur", "Udupi", "Vadodara", "Varanasi", "Vellore", "Vijayawada",
    "Visakhapatnam", "Warangal"
]

trains = []
for i in range(100):
    source = CITIES[i % len(CITIES)]
    # Use two different route offsets so searches cover a broad range of cities.
    offset = 7 if i < len(CITIES) else 13
    destination = CITIES[(i + offset) % len(CITIES)]
    if source.casefold() == destination.casefold():
        destination = CITIES[(i + offset + 1) % len(CITIES)]
    trains.append({
        "id": i + 1,
        "number": str(20001 + i),
        "name": f"{source} {['Express', 'Superfast', 'Intercity', 'Passenger'][i % 4]}",
        "source": source,
        "destination": destination,
        "distance": 120 + ((i * 137) % 1480),
        "rate": [0.80, 1.00, 1.20, 1.50][i % 4],
        "total_seats": [40, 50, 60, 80][i % 4]
    })
# Additional Andhra Pradesh sample trains
# These are demonstration records, NOT official railway schedules.

AP_TRAINS = [
    ("Vijayawada", "Visakhapatnam", "Coastal Express", 350, 1.00, 80),
    ("Visakhapatnam", "Vijayawada", "Coastal Express Return", 350, 1.00, 80),
    ("Vijayawada", "Tirupati", "Tirumala Express", 410, 1.20, 80),
    ("Tirupati", "Vijayawada", "Tirumala Express Return", 410, 1.20, 80),
    ("Guntur", "Visakhapatnam", "Andhra Intercity", 380, 1.00, 60),
    ("Visakhapatnam", "Guntur", "Andhra Intercity Return", 380, 1.00, 60),
    ("Vijayawada", "Guntur", "Krishna Passenger", 35, 0.80, 50),
    ("Guntur", "Vijayawada", "Krishna Passenger Return", 35, 0.80, 50),
    ("Vijayawada", "Rajahmundry", "Godavari Express", 160, 1.00, 80),
    ("Rajahmundry", "Vijayawada", "Godavari Express Return", 160, 1.00, 80),
    ("Visakhapatnam", "Rajahmundry", "Eastern Andhra Express", 190, 1.00, 60),
    ("Rajahmundry", "Visakhapatnam", "Eastern Andhra Express Return", 190, 1.00, 60),
    ("Nellore", "Tirupati", "Sri Venkateswara Express", 130, 1.00, 60),
    ("Tirupati", "Nellore", "Sri Venkateswara Express Return", 130, 1.00, 60),
    ("Ongole", "Vijayawada", "Prakasam Intercity", 120, 1.00, 60),
    ("Vijayawada", "Ongole", "Prakasam Intercity Return", 120, 1.00, 60),
    ("Kurnool", "Guntur", "Rayalaseema Express", 250, 1.20, 60),
    ("Guntur", "Kurnool", "Rayalaseema Express Return", 250, 1.20, 60),
    ("Anantapur", "Tirupati", "Ananta Intercity", 250, 1.00, 50),
    ("Tirupati", "Anantapur", "Ananta Intercity Return", 250, 1.00, 50),
]

for source, destination, name, distance, rate, seats in AP_TRAINS:
    train_id = len(trains) + 1

    trains.append({
        "id": train_id,
        "number": str(20101 + train_id - 101),
        "name": name,
        "source": source,
        "destination": destination,
        "distance": distance,
        "rate": rate,
        "total_seats": seats
    })

next_user_id = 1
next_train_id = len(trains) + 1
next_ticket_id = 1001
initial_admin_created = False


def validate_username(username):
    username = username.strip()
    if not username or username[0] in ". " or username[-1] in ". ":
        return False
    if username.count(".") > 1:
        return False
    return re.fullmatch(r"[A-Za-z. ]+", username) is not None


def validate_password(password):
    if len(password) != 10 or not password.isascii():
        return False
    upper = sum(ch.isupper() and ch.isalpha() for ch in password)
    lower = sum(ch.islower() and ch.isalpha() for ch in password)
    digits = sum(ch.isdigit() for ch in password)
    special = sum(not ch.isalnum() for ch in password)
    return upper == 1 and lower == 4 and digits == 4 and special == 1


def get_user(user_id):
    return next((u for u in users if u["id"] == user_id), None)


def get_train(train_id):
    return next((t for t in trains if t["id"] == train_id), None)


def get_ticket(ticket_id):
    return next((b for b in bookings if b["ticket_id"] == ticket_id), None)


def available_seats(train):
    booked = {
        b["seat"] for b in bookings
        if b["train_id"] == train["id"] and b["status"] == "Confirmed"
    }
    return [
        seat for seat in range(1, train["total_seats"] + 1)
        if seat not in booked
    ]


def page(title, message="", **kwargs):
    return render_template(
        "index.html",
        title=title,
        message=message,
        user=get_user(session.get("user_id")),
        initial_admin_created=initial_admin_created,
        available_count=lambda train: len(available_seats(train)),
        **kwargs
    )


def login_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        if not session.get("user_id"):
            return redirect("/login")
        if get_user(session.get("user_id")) is None:
            session.clear()
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapper


def admin_required(view):
    @wraps(view)
    def wrapper(*args, **kwargs):
        user = get_user(session.get("user_id"))
        if not user or user["role"] != "Admin":
            return redirect("/login")
        return view(*args, **kwargs)
    return wrapper


@app.route("/")
def home():
    # Public landing page: searching trains does not require an account.
    return page("Railway Reservation System", cities=CITIES, train_count=len(trains))


@app.route("/register", methods=["GET", "POST"])
def register():
    global next_user_id, initial_admin_created

    if request.method == "GET":
        requested_role = request.args.get("role", "Customer")
        return page("Register", requested_role=requested_role)

    role = request.form.get("role", "Customer")
    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if role not in ("Customer", "Admin"):
        return page("Register", "Invalid account type.")

    # Only one initial admin can be created from public registration.
    if role == "Admin" and initial_admin_created:
        return page(
            "Register",
            "Initial admin registration is closed. An existing admin must create more admins."
        )

    if not validate_username(username):
        return page(
            "Register",
            "Invalid username. Use English letters/spaces and at most one dot. "
            "Do not start or end with a dot or space."
        )

    if not validate_password(password):
        return page(
            "Register",
            "Password must be exactly 10 characters: 1 uppercase, "
            "4 lowercase, 4 digits and 1 special character."
        )

    if any(u["username"].casefold() == username.casefold() for u in users):
        return page("Register", "That username already exists.")

    users.append({
        "id": next_user_id,
        "username": username,
        "password": password,
        "role": role
    })
    next_user_id += 1

    if role == "Admin":
        initial_admin_created = True

    return redirect("/login?role=" + role)


@app.route("/admin/register", methods=["GET", "POST"])
@login_required
@admin_required
def register_admin():
    global next_user_id

    if request.method == "GET":
        return page("Create Admin")

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")

    if not validate_username(username):
        return page("Create Admin", "Invalid username.")
    if not validate_password(password):
        return page(
            "Create Admin",
            "Password must be exactly 10 characters: 1 uppercase, "
            "4 lowercase, 4 digits and 1 special character."
        )
    if any(u["username"].casefold() == username.casefold() for u in users):
        return page("Create Admin", "That username already exists.")

    users.append({
        "id": next_user_id,
        "username": username,
        "password": password,
        "role": "Admin"
    })
    next_user_id += 1
    return redirect("/admin")


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        requested_role = request.args.get("role", "Customer")
        if requested_role not in ("Customer", "Admin"):
            requested_role = "Customer"
        return page("Login", requested_role=requested_role, next_url=request.args.get("next", ""))

    username = request.form.get("username", "").strip()
    password = request.form.get("password", "")
    role = request.form.get("role", "Customer")

    user = next((
        u for u in users
        if u["username"].casefold() == username.casefold()
        and u["password"] == password
        and u["role"] == role
    ), None)

    if user is None:
        return page(
            "Login",
            "Invalid username, password or account type. "
            "Make sure the account type matches the account you registered.",
            requested_role=role, next_url=request.args.get("next", "")
        )

    session.clear()
    session["user_id"] = user["id"]
    next_url = request.args.get("next", "") or request.form.get("next_url", "")
    if next_url.startswith("/") and not next_url.startswith("//") and role == "Customer":
        return redirect(next_url)
    return redirect("/admin" if role == "Admin" else "/customer")


@app.route("/logout")
def logout():
    session.clear()
    return redirect("/")


@app.route("/customer")
@login_required
def customer():
    user = get_user(session["user_id"])
    if user["role"] != "Customer":
        return redirect("/admin")

    my_bookings = [b for b in bookings if b["user_id"] == user["id"]]
    return page("Customer Dashboard", bookings_list=my_bookings, trains_list=trains)


@app.route("/search")
def search():
    source = request.args.get("source", "").strip().casefold()
    destination = request.args.get("destination", "").strip().casefold()
    query = request.args.get("query", "").strip().casefold()
    results = []

    for train in trains:
        route_match = bool(
            source and destination
            and train["source"].casefold() == source
            and train["destination"].casefold() == destination
        )
        train_match = bool(
            query and (
                query in train["name"].casefold()
                or query == train["number"].casefold()
            )
        )
        if route_match or train_match:
            item = train.copy()
            item["available"] = len(available_seats(train))
            item["fare"] = round(train["distance"] * train["rate"], 2)
            results.append(item)

    return page("Train Search Results", trains_list=results, source=request.args.get("source", ""), destination=request.args.get("destination", ""), query=request.args.get("query", ""))


@app.route("/seats/<int:train_id>")
def seats(train_id):
    train = get_train(train_id)
    if not train:
        return page("Seat Selection", "Train not found.")
    return page("Seat Selection", train=train, available=available_seats(train))


@app.route("/book", methods=["POST"])
def book():
    if not session.get("user_id") or get_user(session.get("user_id")) is None:
        train_id = request.form.get("train_id", type=int)
        return redirect(f"/login?next=/seats/{train_id}")
    global next_ticket_id
    user = get_user(session["user_id"])
    if user["role"] != "Customer":
        return redirect("/admin")

    train_id = request.form.get("train_id", type=int)
    seat = request.form.get("seat", type=int)
    train = get_train(train_id) if train_id else None

    if not train or seat is None or seat not in available_seats(train):
        return page("Seat Selection", "That train or seat is invalid or no longer available.")

    passenger_name = request.form.get("passenger_name", "").strip()
    phone = request.form.get("phone", "").strip()

    if not passenger_name or not all(part.isalpha() for part in passenger_name.split()):
        return page("Seat Selection", "Enter a valid passenger name using letters and spaces.")
    if not phone.isascii() or not phone.isdigit() or len(phone) != 10:
        return page("Seat Selection", "Enter a valid 10-digit phone number.")

    booking = {
        "ticket_id": next_ticket_id,
        "user_id": user["id"],
        "passenger_name": passenger_name,
        "phone": phone,
        "train_id": train["id"],
        "train_number": train["number"],
        "train_name": train["name"],
        "source": train["source"],
        "destination": train["destination"],
        "distance": train["distance"],
        "seat": seat,
        "fare": round(train["distance"] * train["rate"], 2),
        "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "status": "Confirmed"
    }
    bookings.append(booking)
    next_ticket_id += 1
    return page("Your Ticket", ticket=booking)


@app.route("/bookings")
@login_required
def my_bookings():
    user = get_user(session["user_id"])
    if user["role"] != "Customer":
        return redirect("/admin")
    my_list = [b for b in bookings if b["user_id"] == user["id"]]
    return page("My Bookings", bookings_list=my_list)


@app.route("/cancel/<int:ticket_id>", methods=["POST"])
@login_required
def cancel(ticket_id):
    user = get_user(session["user_id"])
    booking = get_ticket(ticket_id)

    if not booking:
        return page("Cancellation", "Ticket not found.")
    if user["role"] != "Admin" and booking["user_id"] != user["id"]:
        return page("Cancellation", "You cannot cancel another user's ticket.")
    if booking["status"] != "Confirmed":
        return page("Cancellation", "This ticket is already cancelled.")

    booking["status"] = "Cancelled"
    return redirect("/admin" if user["role"] == "Admin" else "/bookings")


@app.route("/admin")
@login_required
@admin_required
def admin():
    confirmed = [b for b in bookings if b["status"] == "Confirmed"]
    cancelled = [b for b in bookings if b["status"] == "Cancelled"]
    revenue = sum(b["fare"] for b in confirmed)
    return page(
        "Admin Dashboard",
        trains_list=trains,
        bookings_list=bookings,
        cancelled_list=cancelled,
        revenue=round(revenue, 2),
        confirmed_count=len(confirmed)
    )


@app.route("/admin/add-train", methods=["GET", "POST"])
@login_required
@admin_required
def add_train():
    global next_train_id

    if request.method == "GET":
        return page("Add Train")

    number = request.form.get("number", "").strip()
    name = request.form.get("name", "").strip()
    source = request.form.get("source", "").strip()
    destination = request.form.get("destination", "").strip()

    try:
        distance = int(request.form.get("distance", ""))
        rate = float(request.form.get("rate", ""))
        total_seats = int(request.form.get("total_seats", ""))
    except ValueError:
        return page("Add Train", "Enter valid numeric values.")

    if not number.isascii() or not number.isdigit():
        return page("Add Train", "Train number must contain digits only.")
    if any(t["number"] == number for t in trains):
        return page("Add Train", "That train number already exists.")
    if not name or not source or not destination:
        return page("Add Train", "All fields are required.")
    if source.casefold() == destination.casefold():
        return page("Add Train", "Source and destination must differ.")
    if distance <= 0 or rate <= 0 or total_seats <= 0:
        return page("Add Train", "Distance, fare rate and seats must be positive.")

    trains.append({
        "id": next_train_id,
        "number": number,
        "name": name,
        "source": source,
        "destination": destination,
        "distance": distance,
        "rate": rate,
        "total_seats": total_seats
    })
    next_train_id += 1
    return redirect("/admin")


@app.route("/admin/update-train/<int:train_id>", methods=["GET", "POST"])
@login_required
@admin_required
def update_train(train_id):
    train = get_train(train_id)
    if not train:
        return page("Update Train", "Train not found.")

    if request.method == "GET":
        return page("Update Train", train=train)

    name = request.form.get("name", "").strip()
    source = request.form.get("source", "").strip()
    destination = request.form.get("destination", "").strip()

    try:
        distance = int(request.form.get("distance", ""))
        rate = float(request.form.get("rate", ""))
        total_seats = int(request.form.get("total_seats", ""))
    except ValueError:
        return page("Update Train", "Enter valid numeric values.", train=train)

    booked_seats = {
        b["seat"] for b in bookings
        if b["train_id"] == train_id and b["status"] == "Confirmed"
    }
    if (
        not name or not source or not destination
        or source.casefold() == destination.casefold()
        or distance <= 0 or rate <= 0 or total_seats <= 0
        or (booked_seats and max(booked_seats) > total_seats)
    ):
        return page(
            "Update Train",
            "Invalid details or new seat capacity conflicts with bookings.",
            train=train
        )

    train.update({
        "name": name, "source": source, "destination": destination,
        "distance": distance, "rate": rate, "total_seats": total_seats
    })
    return redirect("/admin")


@app.route("/admin/delete-train/<int:train_id>", methods=["POST"])
@login_required
@admin_required
def delete_train(train_id):
    train = get_train(train_id)
    if not train:
        return page("Admin Dashboard", "Train not found.")
    if any(
        b["train_id"] == train_id and b["status"] == "Confirmed"
        for b in bookings
    ):
        return page(
            "Admin Dashboard",
            "Cancel confirmed tickets for this train before deleting it.",
            trains_list=trains,
            bookings_list=bookings,
            cancelled_list=[b for b in bookings if b["status"] == "Cancelled"],
            revenue=sum(b["fare"] for b in bookings if b["status"] == "Confirmed"),
            confirmed_count=sum(b["status"] == "Confirmed" for b in bookings)
        )
    trains.remove(train)
    return redirect("/admin")


if __name__ == "__main__":
    app.run(debug=True)
