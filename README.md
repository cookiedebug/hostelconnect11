# HostelConnect — Booking Made Simple

A school-project-ready Flask + SQLite prototype for a Ghana-wide student accommodation platform.

## What is included

### Student
- Browse and search without an account
- Search hostels by region and university
- See currently available rooms near the selected campus
- View prices, rooms, facilities and locations
- See available/unavailable rooms
- Save/favorite accommodation
- Reserve a room through a clearly marked **demo payment flow**
- Report outdated information
- View booking history

### Landlord / Agent
- Dedicated landlord registration/login (active immediately)
- Add accommodation
- Edit owned accommodation and see published status
- Add room types and prices
- Set total and available rooms
- Update room price/availability
- Upload, preview, and remove hostel and room photos (JPG, JPEG, PNG, WEBP, GIF; 5MB each)
- View transactions and student/institution details for their properties

### Administrator
- Suspend or restore landlord accounts when needed
- Approve accommodation listings
- Reject accommodation listings
- Remove listings
- Monitor reports
- View users/listings/verification statistics
- View transaction volume
- Access rental-price and availability analytics

## Run locally

1. Install Python 3.10+.
2. Open a terminal in this project folder.
3. Create a virtual environment:

```bash
python -m venv .venv
```

Windows:
```bash
.venv\Scripts\activate
```

macOS/Linux:
```bash
source .venv/bin/activate
```

4. Install dependencies:

```bash
pip install -r requirements.txt
```

5. Start the application:

```bash
python app.py
```

6. Open:
`http://127.0.0.1:8080/`

The SQLite database is created automatically at `instance/accommodation.db`.

### Run or debug from VS Code without internet

Install the VS Code Python extension and the project dependencies before going offline. Open this folder in VS Code, select **Run HostelConnect (Offline)** in **Run and Debug**, then press **F5**. VS Code starts `app.py` with the project virtual environment, opens the local site at `http://127.0.0.1:8080/`, and keeps the debugger attached. Stop the app with **Shift+F5**. The server only listens on your computer; no internet connection is required.

### Running offline on Windows

Once Python and the dependencies are installed, the app runs without an internet connection. Double-click `run_windows.bat`; it starts the server, waits until it responds, and opens `http://127.0.0.1:8080/` in your browser. Keep the launcher window open while using the app. The site uses a local cover image when a listing's photo is hosted externally, so browsing does not depend on internet images.

### Run tests

Run `python -m unittest discover -v` from the project folder. Tests use a temporary SQLite database and mock the SMS provider, so they do not alter your local database or send real messages. State-changing forms require a session CSRF token; logout uses POST rather than GET.

## Automatic publishing and public browsing

Visitors can use the homepage filters and open published hostel details without registering. The public navigation includes Home, Browse Hostels, Universities, Login, and Sign Up; Sign Up is for landlords. Existing student login and booking/favorite features remain available for existing accounts.

New landlord accounts are active immediately and go directly to their management dashboard. New listings are published immediately after submission. Administrators can suspend landlords, hide or remove listings, and manage reports. The migration adds hostel contact/rules fields, room descriptions/payment/occupied fields, `gender` to users, and `room_id` to photos; existing records are preserved.

## Demo accounts

- Admin: `admin@hostelconnect.local` / `admin123`
- Manager: `manager@hostelconnect.local` / `manager123`
- Student: `student@hostelconnect.local` / `student123`

Change all demo passwords before deployment, and set `HOSTELCONNECT_SECRET_KEY` to a long, random value in the server environment. If it is unset, the app generates an ephemeral key at startup, which signs local sessions but invalidates them whenever the app restarts.

## Important production upgrades

This is intentionally a prototype. Before turning it into the Ghana-wide production platform, add:

- Real payment gateway integration (e.g. a Ghana-supported provider)
- HTTPS and secure secret management
- Strong password and account verification flows
- Email/SMS/WhatsApp notifications
- Image upload storage (cloud object storage)
- Real maps/geocoding
- Manager/agent identity and business verification
- More granular permissions
- Audit logs
- Rate limiting and security monitoring
- PostgreSQL for production scale
- Background jobs
- Automated backups
- Privacy policy, terms, consent and data-retention controls
- Proper tenancy/booking lifecycle (pending, confirmed, checked-in, checked-out, cancelled)
- Subscription/slot billing for hostel owners
- Advertising management for nearby vendors
- Python analytics service using pandas/numpy/scikit-learn
- Mobile app using Flutter or React Native against the same API

## Architecture direction

For the academic prototype:
Browser -> Flask -> SQLite

For the future Ghana-wide system:
Web/Mobile -> Flask/FastAPI API -> PostgreSQL
                         |
                         -> Analytics service (pandas/numpy/scikit-learn)
                         -> Payment provider
                         -> Maps/geocoding
                         -> Notifications
                         -> Image/object storage
