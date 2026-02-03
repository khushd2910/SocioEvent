from flask import Flask, request, render_template
import psycopg2
from flask_cors import CORS
import os
import uuid
from flask import send_from_directory

app = Flask(__name__)
CORS(app)

UPLOAD_FOLDER = "static/uploads"
app.config["UPLOAD_FOLDER"] = UPLOAD_FOLDER

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# ===== PostgreSQL Connection =====
def get_db_connection():
    conn = psycopg2.connect(
        host="localhost",
        database="Event",   # <-- YOUR DB NAME
        user="postgres",    # <-- YOUR USER
        password="pass",    # <-- YOUR PASSWORD
        port=5432
    )
    return conn

@app.route("/")
def home():
    return render_template("home.html")


@app.route("/create_event", methods=["GET", "POST"])
def create_event():
    if request.method == "GET":
        return render_template("create_events.html")

    # --------- Read FORM data ---------
    data = request.form

    event_name = data.get("event_name")
    event_date = data.get("event_date")
    event_time = data.get("event_time")
    categories = data.get("categories")
    event_features = data.get("event_features")
    guest_speaker = data.get("guest_speaker")
    ticket_type = data.get("ticket_type")
    event_description = data.get("event_description")

    # ---- Numeric fields ----
    event_capacity = int(data.get("event_capacity") or 0)

    ticket_price = data.get("ticket_price")
    if ticket_price == "" or ticket_price is None or ticket_type == "free":
        ticket_price = 0
    ticket_price = float(ticket_price)

    # ---- Get multiple images ----
    images = request.files.getlist("event_images")

    try:
        conn = get_db_connection()
        cur = conn.cursor()

        # Insert event first
        cur.execute("""
        INSERT INTO events 
        (event_name, event_date, event_time, categories, event_features, 
         guest_speaker, event_capacity, ticket_type, ticket_price, event_description)
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
        RETURNING id;
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
            event_description
        ))

        event_id = cur.fetchone()[0]

        # ---- Save images & store paths ----
        images = request.files.getlist("event_images")

        for image in images:
            if image and image.filename:
                file_ext = os.path.splitext(image.filename)[1]
                filename = str(uuid.uuid4()) + file_ext   # safe random name
                filepath = os.path.join(app.config["UPLOAD_FOLDER"], filename)

                image.save(filepath)

                # Store ONLY the filename in DB (NOT full path)
                cur.execute(
                    "INSERT INTO event_images (event_id, image_path) VALUES (%s, %s)",
                    (event_id, filename)
                )

        print(f"✅ Image saved: {filepath}")


        conn.commit()
        cur.close()
        conn.close()

        return render_template("event_success.html")

    except Exception as e:
        return f"<h3>Database Error:</h3><pre>{str(e)}</pre>", 500
    
@app.route("/find_events")
def find_events():
    conn = get_db_connection()
    cur = conn.cursor()

    # Get events + one image per event
    cur.execute("""
        SELECT 
            e.id, e.event_name, e.event_date, e.event_time, 
            e.categories, e.ticket_type, e.ticket_price,
            (SELECT image_path 
             FROM event_images 
             WHERE event_id = e.id 
             LIMIT 1) AS image_path
        FROM events e
        ORDER BY e.created_at DESC;
    """)

    events = cur.fetchall()

    cur.close()
    conn.close()

    # Convert to list of dicts for Jinja
    event_list = []
    for e in events:
        event_list.append({
            "id": e[0],
            "event_name": e[1],
            "event_date": e[2],
            "event_time": e[3],
            "categories": e[4],
            "ticket_type": e[5],
            "ticket_price": e[6],
            "image_path": e[7] or "static/default.jpg"
        })

    return render_template("find_events.html", events=event_list)

@app.route("/event/<int:event_id>")
def event_detail(event_id):
    conn = get_db_connection()
    cur = conn.cursor()

    # 1️⃣ Get the event
    cur.execute("SELECT * FROM events WHERE id = %s;", (event_id,))
    event = cur.fetchone()

    # 2️⃣ Get ALL images (MOST IMPORTANT PART)
    cur.execute("""
        SELECT image_path 
        FROM event_images 
        WHERE event_id = %s;
    """, (event_id,))

    images = cur.fetchall()  # MUST be fetchall()

    cur.close()
    conn.close()

    # 3️⃣ Build clean data for template
    event_data = {
        "id": event[0],
        "event_name": event[1],
        "event_date": event[2],
        "event_time": event[3],
        "categories": event[4],
        "event_features": event[5],
        "guest_speaker": event[6],
        "event_capacity": event[7],
        "ticket_type": event[8],
        "ticket_price": event[9],
        "event_description": event[10],
        "images": [row[0] for row in images]  # 🔥 CRITICAL FIX
    }

    print("IMAGES SENT TO TEMPLATE:", event_data["images"])  # DEBUG

    return render_template("event_detail.html", event=event_data)



@app.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(app.config["UPLOAD_FOLDER"], filename)

if __name__ == "__main__":
    app.run(debug=True, port=5000)
