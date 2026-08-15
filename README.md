# SocioEvent

SocioEvent is a Flask-based event management and ticket booking platform where users can discover events, filter by category or city, book tickets, download tickets as PDFs, and interact with event pages. Admin users can create new events with cover and gallery images, manage ticketing, and publish event details.

## Overview

This project allows:

- Users to sign up and log in
- Event browsing with search and filtering
- Event detail pages with descriptions, gallery, comments, likes, and related events
- Ticket booking and confirmation flow
- PDF ticket download for purchased events
- Admin-only event creation and management
- Profile, settings, notifications, and ticket history management
- Calendar view for upcoming events

## Tech Stack

- Python 3
- Flask
- PostgreSQL
- Jinja2 templates
- HTML, CSS, JavaScript
- ReportLab for PDF generation
- psycopg2 for PostgreSQL connectivity

## Project Structure

```text
SocioEvent/
├── app.py                 # Main Flask application and routes
├── requirements.txt       # Python dependencies
├── templates/             # HTML templates for all pages
├── static/                # Static assets and uploaded media
├── README.md              # Project documentation
└── .gitignore             # Git ignore rules
```

## Features

### For Users

- Explore upcoming events on the homepage
- Search events by keyword or location
- Filter by category, date, price, city, and sort option
- View complete event details
- Like an event and add comments
- Book tickets and see purchased bookings in account history
- Download ticket PDFs
- Cancel a booked ticket if needed
- View notifications and account dashboard

### For Admins

- Create event listings with detailed metadata
- Upload cover image, card image, and gallery images
- Set event date, time, category, capacity, price, location, and registration deadline
- Publish online or offline event information
- Manage ticket sales and access event creation portal

## Prerequisites

Before running the app, make sure you have:

- Python 3.10 or newer
- PostgreSQL installed and running
- Access to a PostgreSQL database named `Event`
- A PostgreSQL user with username `postgres` and password `pass`

## Setup Instructions

1. Clone the repository:

```bash
git clone <repository-url>
cd SocioEvent
```

2. Create a virtual environment:

```bash
python -m venv venv
source venv/bin/activate
```

On Windows:

```bash
venv\Scripts\activate
```

3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Create the PostgreSQL database and ensure the credentials match the application config in `app.py`:

- Host: `localhost`
- Database: `Event`
- User: `postgres`
- Password: `pass`
- Port: `5432`

5. Create the required tables in PostgreSQL. The app depends on tables such as:

```sql
CREATE TABLE users (
    id SERIAL PRIMARY KEY,
    full_name VARCHAR(255),
    username VARCHAR(255) UNIQUE,
    email VARCHAR(255) UNIQUE,
    phone VARCHAR(20) UNIQUE,
    password VARCHAR(255),
    role VARCHAR(50),
    location VARCHAR(255),
    bio TEXT,
    date_of_birth DATE,
    profile_image VARCHAR(255)
);

CREATE TABLE events (
    event_id SERIAL PRIMARY KEY,
    event_name VARCHAR(255),
    event_date DATE,
    event_time TIME,
    categories VARCHAR(255),
    event_features TEXT,
    guest_speaker VARCHAR(255),
    event_capacity INT,
    ticket_type VARCHAR(50),
    ticket_price NUMERIC(10,2),
    event_description TEXT,
    event_address VARCHAR(255),
    event_city VARCHAR(255),
    event_state VARCHAR(255),
    age_limit VARCHAR(100),
    event_language VARCHAR(100),
    reg_deadline DATE,
    meeting_link TEXT,
    online_platform VARCHAR(255),
    social_instagram VARCHAR(255),
    event_website VARCHAR(255),
    whatsapp_group VARCHAR(255),
    youtube_link VARCHAR(255),
    tickets_sold INT DEFAULT 0,
    view_count INT DEFAULT 0,
    like_count INT DEFAULT 0
);

CREATE TABLE event_images (
    id SERIAL PRIMARY KEY,
    event_id INT REFERENCES events(event_id),
    image_path VARCHAR(255),
    image_type VARCHAR(50)
);

CREATE TABLE myticket_user (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    event_id INT REFERENCES events(event_id),
    payment_method VARCHAR(100)
);

CREATE TABLE myticket_admin (
    id SERIAL PRIMARY KEY,
    admin_id INT REFERENCES users(id),
    event_id INT REFERENCES events(event_id),
    payment_method VARCHAR(100)
);

CREATE TABLE event_comments (
    id SERIAL PRIMARY KEY,
    event_id INT REFERENCES events(event_id),
    user_id INT REFERENCES users(id),
    user_role VARCHAR(50),
    comment TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE event_likes (
    id SERIAL PRIMARY KEY,
    user_id INT REFERENCES users(id),
    event_id INT REFERENCES events(event_id),
    UNIQUE (user_id, event_id)
);
```

> Note: This project currently assumes a local PostgreSQL setup and hardcoded database credentials in the application code.

## Run the Application

Start the Flask app:

```bash
python app.py
```

Then open the app in your browser:

```text
http://localhost:5000
```

## Default Admin Credentials

The app includes default admin validation values for organizer sign-up:

- Username: `admin123`
- Password: `admin@123`
- Verification code: `EVENT-ADMIN-2026`

## Notes

- Uploaded images are stored in `static/uploads`.
- PDFs for tickets are generated dynamically with ReportLab.
- The app uses session-based login and role-based access logic for clients and admins.
- This project is intended for local development and can be extended for production use with environment variables, hashed passwords, and deployment configuration.

## License

This project is intended for educational and development purposes. Add your preferred license if you plan to share or distribute it publicly.

## Future Improvements

- Add environment variable configuration
- Implement password hashing using Werkzeug security
- Improve admin dashboard capabilities
- Add REST API support
- Add unit and integration testing
- Deploy to a cloud hosting service
