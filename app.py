import os
import re
import time
import psycopg2
from datetime import date
from flask import Flask, jsonify, request, render_template, redirect, session, url_for, abort, flash
from datetime import datetime
import calendar
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from flask import send_file
import io
from datetime import datetime
import re
from werkzeug.utils import secure_filename


app = Flask(__name__)
app.secret_key = "supersecretkey123"  # TODO: change in production
ADMIN_SECRET = "EVENT-ADMIN-2026"
app.jinja_env.globals['now'] = datetime.now
event_index = {}

# ================= CONFIG =================
UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = os.path.join(app.root_path, "static", "uploads")


if not os.path.exists(UPLOAD_FOLDER):
    os.mkdir(UPLOAD_FOLDER)

# Predefined admin credentials for signup
ADMIN_USERNAME = "admin123"
ADMIN_PASSWORD = "admin@123"

# ================= DATABASE =================
def get_db_connection():
    return psycopg2.connect(
        host="localhost",
        database="Event",
        user="postgres",
        password="pass",
        port=5432
    )

# ============== HELPER DECORATORS ==============
def login_required(f):
    def wrapper(*args, **kwargs):
        if not session.get("user"):
            return redirect("/login")
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper


def admin_required(f):
    def wrapper(*args, **kwargs):
        if not session.get("user") or session["user"].get("role") != "admin":
            return "Access Denied! Admin only.", 403
        return f(*args, **kwargs)
    wrapper.__name__ = f.__name__
    return wrapper

def build_event_index():
    global event_index
    event_index.clear()

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT event_id, event_name, categories, event_address
        FROM events;
    """)

    rows = cur.fetchall()

    for r in rows:
        event_id, name, category, address = r

        text = f"{name} {category} {address}".lower()

        for word in text.split():
            if word not in event_index:
                event_index[word] = set()
            event_index[word].add(event_id)

    cur.close()
    conn.close()


def time_ago(dt):
    if not dt:
        return ""

    now = datetime.now()
    diff = now - dt

    seconds = int(diff.total_seconds())

    if seconds < 60:
        return f"{seconds} second{'s' if seconds != 1 else ''} ago"

    minutes = seconds // 60
    if minutes < 60:
        return f"{minutes} minute{'s' if minutes != 1 else ''} ago"

    hours = minutes // 60
    if hours < 24:
        return f"{hours} hour{'s' if hours != 1 else ''} ago"

    days = hours // 24
    if days < 30:
        return f"{days} day{'s' if days != 1 else ''} ago"

    months = days // 30
    if months < 12:
        return f"{months} month{'s' if months != 1 else ''} ago"

    years = months // 12
    return f"{years} year{'s' if years != 1 else ''} ago"


app.jinja_env.filters["time_ago"] = time_ago



# ================= ROUTES =================
@app.route("/")
def home():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT 
            e.event_id,
            e.event_name,
            e.event_date,
            e.event_time,
            e.categories,
            COALESCE(
                (SELECT image_path 
                 FROM event_images 
                 WHERE event_id = e.event_id 
                 LIMIT 1),
                'default.jpg'
            ) AS image_path
        FROM events e
        WHERE 
            e.event_date > CURRENT_DATE
            OR (e.event_date = CURRENT_DATE AND e.event_time >= CURRENT_TIME)
        ORDER BY e.event_date ASC, e.event_time ASC
        LIMIT 7;
    """)

    upcoming_events = cur.fetchall()

    cur.execute("SELECT DISTINCT categories FROM events;")
    categories = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "home.html",
        upcoming_events=upcoming_events,
        categories=categories
    )


# ---------------- SEARCH ----------------
@app.route("/search")
def search():
    query = request.args.get("q", "").strip()

    if not query:
        return redirect("/find_events")

    return redirect(f"/find_events?q={query}")

# ---------------- CATEGORY FILTER ----------------
@app.route("/category/<category>")
def filter_by_category(category):
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT e.event_id, e.event_name, e.event_date, i.image_path
        FROM events e
        LEFT JOIN event_images i ON e.event_id = i.event_id
        WHERE e.categories = %s;
    """, (category,))

    events = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("find_events.html", events=events)

# ---------------- CREATE EVENT (ADMIN ONLY) ----------------
@app.route("/create_event", methods=["GET", "POST"])
@admin_required
def create_event():
    if request.method == "GET":
        return render_template("create_events.html")

    form = request.form

    event_name = form.get("event_name")
    event_date = form.get("event_date")
    event_time = form.get("event_time")
    categories = form.get("categories")
    event_features = form.get("event_features")
    guest_speaker = form.get("guest_speaker")
    ticket_type = form.get("ticket_type")
    event_description = form.get("event_description")
    event_address = form.get("event_address")
    age_limit = form.get("age_limit")
    event_language = form.get("event_language")


    capacity_text = form.get("event_capacity", "")
    event_capacity = int(capacity_text) if capacity_text.strip() else 0

    ticket_price_text = form.get("ticket_price", "")
    ticket_price = 0.0 if ticket_price_text.strip() == "" or ticket_type == "free" else float(ticket_price_text)

    images = request.files.getlist("event_images")
    images = [img for img in images if img and img.filename]



    try:
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("""
            INSERT INTO events (
                event_name, event_date, event_time, categories, event_features,
                guest_speaker, event_capacity, ticket_type, ticket_price,
                event_description, event_address, age_limit, event_language
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            RETURNING event_id;
        """, (
                event_name,
                event_date,
                event_time,
                categories,
                event_features,
                guest_speaker,
                event_capacity,
                ticket_type,
                ticket_price,
                event_description,
                event_address,
                age_limit,
                event_language
            ))


        event_id = cur.fetchone()[0]

        for image in images:
            filename = image.filename
            if filename:
                name, ext = os.path.splitext(filename)
                new_filename = f"{name}_{int(time.time())}{ext}"
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], new_filename)
                image.save(filepath)

                cur.execute(
                    "INSERT INTO event_images (event_id, image_path) VALUES (%s, %s)",
                    (event_id, new_filename)
                )

        conn.commit()
        cur.close()
        conn.close()

        return render_template("event_success.html")

    except Exception as e:
        return f"<h3>Database Error:</h3><pre>{str(e)}</pre>", 500

# ---------------- FIND EVENTS ----------------
@app.route("/find_events")
def find_events():
    search_query = request.args.get("q", "").lower().strip()
    category = request.args.get("category", "").strip()
    date_filter = request.args.get("date", "").strip()
    price_filter = request.args.get("price", "").strip()
    city = request.args.get("city", "").strip()
    sort_option = request.args.get("sort", "").strip()

    conn = get_db_connection()
    cur = conn.cursor()

    base_query = """
        SELECT 
        e.event_id,
        e.event_name,
        e.event_date,
        e.event_time,
        e.categories,
        e.ticket_type,
        e.ticket_price,
        e.event_address,
        e.view_count,
        (
            SELECT image_path
            FROM event_images img
            WHERE img.event_id = e.event_id
            ORDER BY img.id ASC
            LIMIT 1
        ) AS image_path
        FROM events e
        WHERE 
        (
            e.event_date > CURRENT_DATE
            OR 
            (e.event_date = CURRENT_DATE AND e.event_time >= CURRENT_TIME)
        )
        AND (
            %s = ''
            OR LOWER(e.event_name) LIKE %s
            OR LOWER(e.categories) LIKE %s
            OR LOWER(e.event_address) LIKE %s
        )
    """

    params = []

    params.extend([
        search_query,
        f"%{search_query}%",
        f"%{search_query}%",
        f"%{search_query}%"
    ])

    # CATEGORY FILTER
    if category and category.lower() != "all":
        base_query += " AND e.categories = %s"
        params.append(category)

    # DATE FILTER
    if date_filter == "today":
        base_query += " AND e.event_date = CURRENT_DATE"

    elif date_filter == "weekend":
        base_query += """
            AND e.event_date >= CURRENT_DATE
            AND EXTRACT(DOW FROM e.event_date) IN (6,0)
            AND e.event_date <= CURRENT_DATE + INTERVAL '7 days'
        """

    elif date_filter == "month":
        base_query += """
            AND e.event_date >= CURRENT_DATE
            AND e.event_date < CURRENT_DATE + INTERVAL '30 days'
        """

    # PRICE FILTER
    if price_filter == "free":
        base_query += " AND e.ticket_type = 'free'"

    elif price_filter == "paid":
        base_query += " AND e.ticket_type = 'paid'"

    elif price_filter == "under500":
        base_query += " AND e.ticket_price < 500"

    elif price_filter == "500-2000":
        base_query += " AND e.ticket_price BETWEEN 500 AND 2000"

    elif price_filter == "2000plus":
        base_query += " AND e.ticket_price > 2000"

    # LOCATION FILTER
    if city:
        base_query += " AND e.event_address ILIKE %s"
        params.append(f"%{city}%")

    # SORTING
    if sort_option == "date":
        base_query += " ORDER BY e.event_date ASC, e.event_time ASC"

    elif sort_option == "views":
        base_query += " ORDER BY e.view_count DESC NULLS LAST"

    elif sort_option == "likes":
        base_query += " ORDER BY e.like_count DESC NULLS LAST"

    elif sort_option == "purchases":
        base_query += """
            ORDER BY (
                SELECT COUNT(*) 
                FROM myticket_user t 
                WHERE t.event_id = e.event_id
            ) DESC
        """
    else:
        base_query += " ORDER BY e.event_date ASC, e.event_time ASC"

    cur.execute(base_query, params)
    events = cur.fetchall()

    # TRENDING QUERY (UPDATED WITH view_count)
    trending_query = """
        SELECT 
            e.event_id, 
            e.event_name, 
            e.event_date, 
            e.event_time, 
            e.categories, 
            e.ticket_type, 
            e.ticket_price, 
            e.event_address,
            e.view_count,
            (SELECT image_path 
             FROM event_images 
             WHERE event_id = e.event_id 
             LIMIT 1)
        FROM events e
        LEFT JOIN myticket_user t 
            ON e.event_id = t.event_id
        WHERE 
            (
                e.event_date > CURRENT_DATE
                OR 
                (e.event_date = CURRENT_DATE AND e.event_time >= CURRENT_TIME)
            )
        GROUP BY 
            e.event_id,
            e.event_name,
            e.event_date,
            e.event_time,
            e.categories,
            e.ticket_type,
            e.ticket_price,
            e.event_address,
            e.view_count
        ORDER BY COUNT(t.id) DESC, e.event_date ASC
        LIMIT 5;
    """

    cur.execute(trending_query)
    trending = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "find_events.html",
        events=events,
        trending=trending,
        selected_category=category,
        selected_date=date_filter,
        selected_price=price_filter,
        selected_city=city,
        selected_sort=sort_option,
        search_query=search_query
    )




# ---------------- EVENT DETAIL ----------------
@app.route("/event/<int:event_id>")
def event_detail(event_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # ✅ 1. Update view count
    cur.execute("""
        UPDATE events
        SET view_count = COALESCE(view_count, 0) + 1
        WHERE event_id = %s
    """, (event_id,))
    conn.commit()

    # ✅ 2. Fetch main event
    cur.execute("""
        SELECT 
            event_id,
            event_name,
            event_date,
            event_time,
            categories,
            event_capacity,
            ticket_type,
            ticket_price,
            event_features,
            event_description,
            guest_speaker,
            event_address,
            age_limit,
            event_language,
            like_count
        FROM events
        WHERE event_id = %s;
    """, (event_id,))

    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return "Event not found", 404

    # ✅ 3. Fetch event images
    cur.execute(
    "SELECT image_path FROM event_images WHERE event_id = %s ORDER BY id ASC;",
    (event_id,)
)

    rows = cur.fetchall()
    images = [r[0] for r in rows]

    event = {
        "id": row[0],
        "event_name": row[1],
        "event_date": row[2],
        "event_time": row[3],
        "categories": row[4],
        "event_capacity": row[5],
        "ticket_type": row[6],
        "ticket_price": row[7],
        "event_features": row[8],
        "event_description": row[9],
        "guest_speaker": row[10],
        "event_address": row[11],
        "age_limit": row[12],
        "event_language": row[13],
        "like_count": row[14] if row[14] else 0,
        "images": images
    }

    # Fetch related events
    cur.execute("""
        SELECT event_id, event_name, event_date, event_time,
            event_address, ticket_price, ticket_type
        FROM events
        WHERE categories = %s
        AND event_id != %s
        ORDER BY event_date ASC
        LIMIT 4;
    """, (event["categories"], event_id))


    related_rows = cur.fetchall()
    related_events = []

    for rel in related_rows:
        rel_id = rel[0]

        cur.execute("""
            SELECT image_path
            FROM event_images
            WHERE event_id = %s
            LIMIT 1;
        """, (rel_id,))

        img_row = cur.fetchone()
        image = img_row[0] if img_row else "default.jpg"

        related_events.append({
            "id": rel[0],
            "event_name": rel[1],
            "event_date": rel[2],
            "event_time": rel[3],
            "event_address": rel[4],
            "ticket_price": rel[5],
            "ticket_type": rel[6],
            "image": image
        })


    # ✅ 5. Fetch comments
    cur.execute("""
        SELECT 
        c.comment,
        c.created_at,
        u.full_name AS username
    FROM event_comments c
    LEFT JOIN users u
        ON c.user_id = u.id
    WHERE c.event_id = %s
    ORDER BY c.created_at DESC;
        """, (event_id,))
    
    comments = cur.fetchall()

    cur.close()
    conn.close()

    return render_template(
        "event_detail.html",
        event=event,
        comments=comments,
        related_events=related_events
    )



@app.route("/buy_ticket/<int:event_id>", methods=["GET"])
@login_required
def buy_ticket(event_id):
    back = request.args.get("back")
    user_id = session["user"]["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    # Check event capacity
    cur.execute("""
        SELECT event_id, event_capacity, tickets_sold
        FROM events
        WHERE event_id = %s
        FOR UPDATE;
    """, (event_id,))
    row = cur.fetchone()

    if not row:
        cur.close()
        conn.close()
        return "Event not found", 404

    event_id_db, capacity, sold = row
    sold = sold or 0

    if sold >= capacity:
        cur.close()
        conn.close()
        return "⚠️ This event is SOLD OUT!"

    # Insert ticket
    cur.execute("""
        INSERT INTO myticket_user (user_id, event_id, payment_method)
        VALUES (%s, %s, %s);
    """, (user_id, event_id, "N/A"))

    # Increment tickets sold
    cur.execute("""
        UPDATE events
        SET tickets_sold = COALESCE(tickets_sold, 0) + 1
        WHERE event_id = %s;
    """, (event_id,))

    cur.execute("""
        SELECT event_id, event_name, event_date, ticket_price
        FROM events WHERE event_id = %s;
    """, (event_id,))

    event = cur.fetchone()

    cur.close()
    conn.close()

    if not event:
        return "Event not found", 404

    return render_template(
        "buyticket.html",
        event={
            "id": event[0],
            "name": event[1],
            "date": event[2],
            "price": event[3]
        },
        back=back
    )


@app.route("/confirm_ticket/<int:event_id>", methods=["POST"])
@login_required
def confirm_ticket(event_id):
    user = session["user"]
    payment_method = request.form.get("payment")

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Lock event row
        cur.execute("""
            SELECT event_capacity, COALESCE(tickets_sold, 0)
            FROM events
            WHERE event_id = %s
            FOR UPDATE;
        """, (event_id,))

        row = cur.fetchone()
        if not row:
            conn.rollback()
            return "Event not found", 404

        capacity, sold = row

        if sold >= capacity:
            conn.rollback()
            return "⚠️ This event is SOLD OUT!"

        # Insert ticket
        if user["role"] == "client":
            cur.execute("""
                INSERT INTO myticket_user (user_id, event_id, payment_method)
                VALUES (%s, %s, %s);
            """, (user["id"], event_id, payment_method))
        else:
            cur.execute("""
                INSERT INTO myticket_admin (admin_id, event_id, payment_method)
                VALUES (%s, %s, %s);
            """, (user["id"], event_id, payment_method))

        # Increase sold count
        cur.execute("""
            UPDATE events
            SET tickets_sold = tickets_sold + 1
            WHERE event_id = %s;
        """, (event_id,))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return f"Error: {str(e)}", 500

    finally:
        cur.close()
        conn.close()

    return redirect("/tickets")



# ---------------- SIGNUP ----------------
@app.route("/signup", methods=["GET", "POST"])
def signup():
    if request.method == "POST":

        full_name = request.form["full_name"]
        username = request.form.get("username", "").strip()

        if not username:
            flash("Username is required", "danger")
            return redirect(url_for("signup"))
        email = request.form["email"].strip().lower()
        phone = request.form["phone"].strip()
        if not phone.isdigit() or len(phone) != 10:
            flash("Phone number must be exactly 10 digits", "danger")
            return redirect(url_for("signup"))
        password = request.form["password"]
        password_regex = re.compile(
            r'^(?=.*[a-z])(?=.*[A-Z])(?=.*\d)(?=.*[@$!%*?&]).{8,}$'
            )

        if not password_regex.match(password):
            flash(
                "Password must be at least 8 characters long and include uppercase, lowercase, number, and special character",
                "danger"
            )
            return redirect(url_for("signup"))
        confirm_password = request.form["confirm_password"]
        role = request.form["role"]
        location = request.form.get("location")
        bio = request.form.get("bio")
        date_of_birth = request.form.get("date_of_birth") or None

        errors = {}

        # -------- PASSWORD CHECK --------
        if password != confirm_password:
            errors["password"] = "Passwords do not match"

        # -------- ADMIN CHECK --------
        if role == "admin":
            if (
                request.form.get("admin_username") != "admin123" or
                request.form.get("admin_password") != "admin@123" or
                request.form.get("verification_code") != "EVENT-ADMIN-2026"
            ):
                errors["admin"] = "Invalid organizer verification details"

        # -------- DB CHECKS --------
        conn = get_db_connection()
        cur = conn.cursor()

        cur.execute("SELECT 1 FROM users WHERE email = %s", (email,))
        if cur.fetchone():
            errors["email"] = "Email already exists"

        cur.execute("SELECT 1 FROM users WHERE phone = %s", (phone,))
        if cur.fetchone():
            errors["phone"] = "Phone number already exists"

        cur.execute("SELECT 1 FROM users WHERE username = %s", (username,))
        if cur.fetchone():
            errors["username"] = "Username already exists"

        if errors:
            cur.close()
            conn.close()
            return render_template("signup.html", errors=errors)

        # -------- PROFILE IMAGE --------
        profile_image = None
        if "profile_image" in request.files:    
            file = request.files["profile_image"]
            if file and file.filename:
                filename = secure_filename(file.filename)
                path = os.path.join("static/uploads/profiles", filename)
                os.makedirs("static/uploads/profiles", exist_ok=True)
                file.save(path)
                profile_image = filename

        # -------- INSERT --------
        cur.execute("""
            INSERT INTO users
            (full_name, username, email, phone, password, role,
             location, bio, date_of_birth, profile_image)
            VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """, (
            full_name, username, email, phone, password, role,
            location, bio, date_of_birth, profile_image
        ))

        conn.commit()
        cur.close()
        conn.close()

        flash("Account created successfully", "success")
        return redirect(url_for("login"))

    return render_template("signup.html")

@app.route("/register", methods=["POST"])
def register():
    data = request.json

    email = data.get("email", "").strip().lower()
    password = data.get("password", "").strip()
    full_name = data.get("fullName", "").strip()
    username = data.get("username", "").strip()
    phone = data.get("phone", "").strip()
    dob = data.get("date_of_birth") or None
    role = data.get("role", "client")

    # 🔐 Admin verification
    if role == "admin":
        if (
            data.get("adminUser") != ADMIN_USERNAME or
            data.get("adminPass") != ADMIN_PASSWORD
        ):
            return jsonify({"error": "Invalid admin credentials"}), 403

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        cur.execute("""
            INSERT INTO users (
                email,
                password,
                full_name,
                username,
                phone,
                date_of_birth,
                role
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s)
        """, (
            email,
            password,
            full_name,
            username,
            phone,
            dob,
            role
        ))

        conn.commit()

    except psycopg2.errors.UniqueViolation as e:
        conn.rollback()
        return jsonify({
            "error": "Email / username / phone already exists"
        }), 409

    finally:
        cur.close()
        conn.close()

    return jsonify({"message": "User registered successfully"}), 201
# ---------------- LOGIN (DB-BASED SESSION) ----------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "GET":
        return render_template("login.html")

    email = request.form["email"].strip()
    password = request.form["password"].strip()

    conn = get_db_connection()
    cur = conn.cursor()

    # ✅ SINGLE USERS TABLE
    cur.execute("""
        SELECT id, full_name, email, role, password
        FROM users
        WHERE LOWER(email) = LOWER(%s)
    """, (email,))

    user = cur.fetchone()

    cur.close()
    conn.close()

    if not user:
        flash("Invalid email or password", "error")
        return render_template("login.html")

    db_password = user[4]

    # ❗ Plain text comparison (as you requested)
    if db_password != password:
        flash("Invalid email or password", "error")
        return render_template("login.html")

    # ✅ LOGIN SUCCESS
    session["user"] = {
        "id": user[0],
        "name": user[1],
        "email": user[2],
        "role": user[3]
    }

    return redirect("/")

@app.route("/profile")
def profile():
    if "user" not in session:
        return redirect(url_for("login"))

    user_id = session["user"]["id"]
    role = session["user"]["role"]

    conn = get_db_connection()
    cur = conn.cursor()

    # 🔹 Fetch profile info
    cur.execute("""
        SELECT full_name, email
        FROM users
        WHERE id = %s AND role = %s
    """, (user_id, role))

    user = cur.fetchone()

    # 🔹 Tickets Bought (from myticket_admin table)
    tickets_bought = 0
    if role == "admin":
        cur.execute("""
            SELECT COUNT(*) 
            FROM myticket_admin 
            WHERE admin_id = %s
        """, (user_id,))
        tickets_bought = cur.fetchone()[0]

    # 🔹 Comments count
    comments_count = 0
    try:
        cur.execute("""
            SELECT COUNT(*) 
            FROM event_comments 
            WHERE user_id = %s AND user_role = %s
        """, (user_id, role))
        comments_count = cur.fetchone()[0]
    except:
        comments_count = 0

    # 🔹 Events Created (keep 0 if you removed created_by)
    events_created = 0

    cur.close()
    conn.close()

    return render_template(
        "profile.html",
        user=user,
        events_created=events_created,
        tickets_bought=tickets_bought,
        comments_count=comments_count
    )


@app.route("/settings", methods=["GET", "POST"])
def settings():
    if "user" not in session:
        return redirect(url_for("login"))

    user_id = session["user"]["id"]
    role = session["user"]["role"]

    conn = get_db_connection()
    cur = conn.cursor()

    if request.method == "POST":
        full_name = request.form["full_name"]
        email = request.form["email"]
        phone = request.form["phone"]
        location = request.form["location"]
        bio = request.form["bio"]

        cur.execute("""
            UPDATE users
            SET full_name = %s,
                email     = %s,
                phone     = %s,
                location  = %s,
                bio       = %s
            WHERE id = %s
        """, (full_name, email, phone, location, bio, user_id))

        conn.commit()
        return redirect(url_for("profile"))

    cur.execute("""
        SELECT full_name, email, phone, location, bio
        FROM users
        WHERE id = %s AND role = %s
    """, (user_id, role))

    user = cur.fetchone()

    cur.close()
    conn.close()

    return render_template("settings.html", user=user)


# ---------------- LOGOUT ----------------
@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")


# --------------- PROTECTED EXAMPLES ---------------
@app.route("/tickets")
@login_required
def tickets():
    user = session["user"]
    today = date.today()

    conn = get_db_connection()
    cur = conn.cursor()

    if user["role"] == "client":
        query = """
        SELECT 
            t.id AS booking_id,
            e.event_id,
            e.event_name,
            e.event_date,
            e.event_time,
            e.categories,
            t.payment_method,
            (SELECT image_path FROM event_images 
             WHERE event_id = e.event_id LIMIT 1) AS image_path
        FROM myticket_user t
        JOIN events e ON t.event_id = e.event_id
        WHERE t.user_id = %s
        ORDER BY e.event_date ASC, e.event_time ASC;
        """
        cur.execute(query, (user["id"],))

    else:  # admin
        query = """
        SELECT 
            t.id AS booking_id,
            e.event_id,
            e.event_name,
            e.event_date,
            e.event_time,
            e.categories,
            t.payment_method,
            (SELECT image_path FROM event_images 
             WHERE event_id = e.event_id LIMIT 1) AS image_path
        FROM myticket_admin t
        JOIN events e ON t.event_id = e.event_id
        WHERE t.admin_id = %s
        ORDER BY e.event_date ASC, e.event_time ASC;
        """
        cur.execute(query, (user["id"],))

    rows = cur.fetchall()
    cur.close()
    conn.close()

    today_events = []
    upcoming_events = []
    past_events = []

    for r in rows:
        ticket = {
            "booking_id": r[0],
            "event_id": r[1],
            "name": r[2],
            "date": r[3],
            "time": r[4],
            "category": r[5],
            "payment": r[6],
            "image": r[7] if r[7] else "default.jpg"
        }

        if ticket["date"] == today:
            today_events.append(ticket)
        elif ticket["date"] > today:
            upcoming_events.append(ticket)
        else:
            past_events.append(ticket)

    return render_template(
        "tickets.html",
        today_events=today_events,
        upcoming_events=upcoming_events,
        past_events=past_events
    )



@app.route("/download_ticket/<int:booking_id>")
@login_required
def download_ticket(booking_id):
    user = session["user"]

    conn = get_db_connection()
    cur = conn.cursor()

    if user["role"] == "client":
        cur.execute("""
            SELECT
                e.event_name, e.event_date, e.event_time,
                e.event_address, e.categories,
                e.ticket_price, t.payment_method, t.id
            FROM myticket_user t
            JOIN events e ON t.event_id = e.event_id
            WHERE t.id = %s AND t.user_id = %s;
        """, (booking_id, user["id"]))

    else:  # admin
        cur.execute("""
            SELECT
                e.event_name, e.event_date, e.event_time,
                e.event_address, e.categories,
                e.ticket_price, t.payment_method, t.id
            FROM myticket_admin t
            JOIN events e ON t.event_id = e.event_id
            WHERE t.id = %s AND t.admin_id = %s;
        """, (booking_id, user["id"]))

    data = cur.fetchone()
    cur.close()
    conn.close()

    if not data:
        return "Ticket not found", 404

    (
        event_name, event_date, event_time,
        location, category, price,
        payment, booking_id
    ) = data

    buffer = io.BytesIO()
    pdf = canvas.Canvas(buffer, pagesize=A4)
    width, height = A4

    pdf.setFont("Helvetica-Bold", 22)
    pdf.drawCentredString(width / 2, height - 60, "Event Entry Ticket")

    pdf.setFont("Helvetica", 12)
    y = height - 130

    details = [
        f"Event: {event_name}",
        f"Date: {event_date}",
        f"Time: {event_time}",
        f"Location: {location}",
        f"Category: {category}",
        f"Price: ₹{price}",
        f"Payment: {payment}",
        f"Booking ID: {booking_id}",
        f"Attendee: {user['name']}"
    ]

    for d in details:
        pdf.drawString(70, y, d)
        y -= 25

    pdf.setFont("Helvetica-Oblique", 10)
    pdf.drawCentredString(width / 2, 50, "Show this ticket at the event entrance")

    pdf.showPage()
    pdf.save()
    buffer.seek(0)

    return send_file(
        buffer,
        as_attachment=True,
        download_name=f"{event_name}_ticket.pdf",
        mimetype="application/pdf"
    )



@app.route("/cancel_ticket/<int:booking_id>")
@login_required
def cancel_ticket(booking_id):
    user = session["user"]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        if user["role"] == "client":
            cur.execute("""
                DELETE FROM myticket_user
                WHERE id = %s AND user_id = %s
                RETURNING event_id;
            """, (booking_id, user["id"]))

        else:  # admin
            cur.execute("""
                DELETE FROM myticket_admin
                WHERE id = %s AND admin_id = %s
                RETURNING event_id;
            """, (booking_id, user["id"]))

        row = cur.fetchone()
        if not row:
            conn.rollback()
            return "Ticket not found or unauthorized", 404

        event_id = row[0]

        # decrease sold count
        cur.execute("""
            UPDATE events
            SET tickets_sold = GREATEST(tickets_sold - 1, 0)
            WHERE event_id = %s;
        """, (event_id,))

        conn.commit()

    except Exception as e:
        conn.rollback()
        return str(e), 500

    finally:
        cur.close()
        conn.close()

    return redirect("/tickets")


@app.route("/check_create_event")
def check_create_event():
    if not session.get("user"):
        return redirect("/login")

    if session["user"]["role"] == "admin":
        return redirect("/create_event")
    else:
        return render_template("access_denied.html")

@app.route("/community_guidelines")
def community_guidelines():
    return render_template("community_guidelines.html")
    
#accounts
@app.route("/account")
@login_required
def account():
    user = session["user"]

    # Default values (IMPORTANT)
    total = 0
    upcoming = 0
    past = 0

    conn = get_db_connection()
    cur = conn.cursor()

    if user["role"] == "client":
        cur.execute(
            "SELECT COUNT(*) FROM myticket_user WHERE user_id = %s",
            (user["id"],)
        )
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM myticket_user t
            JOIN events e ON t.event_id = e.event_id
            WHERE t.user_id = %s
              AND e.event_date >= CURRENT_DATE
        """, (user["id"],))
        upcoming = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*)
            FROM myticket_user t
            JOIN events e ON t.event_id = e.event_id
            WHERE t.user_id = %s
              AND e.event_date < CURRENT_DATE
        """, (user["id"],))
        past = cur.fetchone()[0]

    elif user["role"] == "admin":
        # Optional admin stats (safe defaults)
        cur.execute("SELECT COUNT(*) FROM events")
        total = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM events
            WHERE event_date >= CURRENT_DATE
        """)
        upcoming = cur.fetchone()[0]

        cur.execute("""
            SELECT COUNT(*) FROM events
            WHERE event_date < CURRENT_DATE
        """)
        past = cur.fetchone()[0]

    cur.close()
    conn.close()

    return render_template(
        "account.html",
        total_tickets=total,
        upcoming_events=upcoming,
        past_events=past
    )
    
@app.route("/edit_profile", methods=["GET", "POST"])
@login_required
def edit_profile():
    user = session["user"]

    if request.method == "POST":
        full_name = request.form.get("full_name").strip()
        password = request.form.get("password").strip()

        conn = get_db_connection()
        cur = conn.cursor()

        if password:
            cur.execute(
                "UPDATE users SET full_name=%s, password=%s WHERE id=%s",
                (full_name, password, user["id"])
            )
        else:
            cur.execute(
                "UPDATE users SET full_name=%s WHERE id=%s",
                (full_name, user["id"])
            )

        conn.commit()
        cur.close()
        conn.close()

        session["user"]["full_name"] = full_name
        return redirect("/account")

    return render_template("edit_profile.html")


@app.route("/notifications")
@login_required
def notifications():
    user = session["user"]

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT e.event_name, e.event_date
        FROM myticket_user t
        JOIN events e ON t.event_id = e.event_id
        WHERE t.user_id = %s
        AND e.event_date >= CURRENT_DATE
        ORDER BY e.event_date ASC
        LIMIT 5;
    """, (user["id"],))

    notifications = cur.fetchall()
    cur.close()
    conn.close()

    return render_template("notifications.html", notifications=notifications)



@app.route("/add_comment/<int:event_id>", methods=["POST"])
@login_required
def add_comment(event_id):
    user = session["user"]
    comment_text = request.form.get("comment")

    if not comment_text or comment_text.strip() == "":
        return redirect(url_for("event_detail", event_id=event_id))

    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        INSERT INTO event_comments (event_id, user_id, user_role, comment)
        VALUES (%s, %s, %s, %s);
    """, (
        event_id,
        user["id"],
        user["role"],
        comment_text.strip()
    ))

    conn.commit()
    cur.close()
    conn.close()

    return redirect(url_for("event_detail", event_id=event_id))


#calendar view

@app.route("/calendar")
def calendar_view():
    conn = get_db_connection()
    cur = conn.cursor()

    cur.execute("""
        SELECT event_id, event_name, event_date
        FROM events
        WHERE event_date >= CURRENT_DATE
        ORDER BY event_date
    """)

    events = cur.fetchall()
    cur.close()
    conn.close()

    today = datetime.now()
    year = today.year
    month = today.month

    # Get number of days in month safely
    total_days = calendar.monthrange(year, month)[1]

    # Get weekday of first day (0=Monday)
    first_weekday = calendar.monthrange(year, month)[0]

    return render_template(
        "calendar.html",
        events=events,
        year=year,
        month=month,
        total_days=total_days,
        first_weekday=first_weekday,

        # ✅ ADDED (required for grey past dates logic)
        today=today.day,
        current_year=today.year,
        current_month=today.month
    )


@app.route("/like_event/<int:event_id>", methods=["POST"])
def like_event(event_id):
    if not session.get("user"):
        return redirect(url_for("login"))

    user_id = session["user"]["id"]

    conn = get_db_connection()
    cur = conn.cursor()

    try:
        # Try inserting like (will fail if already liked)
        cur.execute("""
            INSERT INTO event_likes (user_id, event_id)
            VALUES (%s, %s);
        """, (user_id, event_id))

        # Increase like_count
        cur.execute("""
            UPDATE events
            SET like_count = COALESCE(like_count, 0) + 1
            WHERE event_id = %s;
        """, (event_id,))

        conn.commit()

    except:
        # If already liked, do nothing
        conn.rollback()

    cur.close()
    conn.close()

    return redirect(url_for("event_detail", event_id=event_id))


with app.app_context():
    build_event_index()


# ---------------- RUN APP ----------------
if __name__ == "__main__":
    app.run(debug=True, port=5000)
