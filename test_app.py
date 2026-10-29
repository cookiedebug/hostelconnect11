import tempfile
import unittest
from datetime import date, timedelta
from pathlib import Path

import app as app_module
from app import app, get_db
from app import media_url


class AccommodationFilterTests(unittest.TestCase):
    def setUp(self):
        self.original_db_path = app_module.DB_PATH
        self.temp_dir = tempfile.TemporaryDirectory()
        app_module.DB_PATH = Path(self.temp_dir.name) / "accommodation.db"
        app_module.init_db()
        self.client = app.test_client()
        self.csrf_token = "test-csrf-token"
        with self.client.session_transaction() as session:
            session["_csrf_token"] = self.csrf_token

    def tearDown(self):
        app_module.DB_PATH = self.original_db_path
        self.temp_dir.cleanup()

    def post(self, path, **kwargs):
        data = kwargs.pop("data", None) or {}
        if isinstance(data, dict):
            data.setdefault("_csrf_token", self.csrf_token)
        return self.client.open(path, method="POST", data=data, **kwargs)

    def test_post_without_csrf_token_is_rejected(self):
        response = self.client.post("/report/1", data={"reason": "Outdated"})
        self.assertEqual(response.status_code, 400)

    def test_logout_requires_post(self):
        response = self.client.get("/logout")
        self.assertEqual(response.status_code, 405)

    def test_favorite_does_not_redirect_to_external_referrer(self):
        db = get_db()
        student = db.execute(
            "SELECT id FROM users WHERE email='student@hostelconnect.local'"
        ).fetchone()
        hostel = db.execute("SELECT id FROM hostels ORDER BY id LIMIT 1").fetchone()
        db.close()
        with self.client.session_transaction() as session:
            session["user_id"] = student["id"]

        response = self.post(
            f"/favorite/{hostel['id']}",
            headers={"Referer": "https://attacker.example/"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(response.headers["Location"], "/")

    def test_room_and_hostel_deletion_preserve_booking_history(self):
        db = get_db()
        manager = db.execute(
            "SELECT id FROM users WHERE email='manager@hostelconnect.local'"
        ).fetchone()
        admin = db.execute(
            "SELECT id FROM users WHERE email='admin@hostelconnect.local'"
        ).fetchone()
        student = db.execute(
            "SELECT id FROM users WHERE email='student@hostelconnect.local'"
        ).fetchone()
        room = db.execute(
            """SELECT r.id, h.id hostel_id FROM rooms r
               JOIN hostels h ON h.id=r.hostel_id
               WHERE h.manager_id=? ORDER BY r.id LIMIT 1""",
            (manager["id"],),
        ).fetchone()
        reference = "DELETE-GUARD-TEST-001"
        db.execute(
            """INSERT INTO bookings(
                   room_id, hostel_id, student_id, booking_reference, amount, status, created_at
               ) VALUES(?,?,?,?,?,'pending',?)""",
            (
                room["id"],
                room["hostel_id"],
                student["id"],
                reference,
                500,
                app_module.now(),
            ),
        )
        db.commit()
        db.close()

        with self.client.session_transaction() as session:
            session["user_id"] = manager["id"]
        room_response = self.post(
            f"/manager/room/{room['id']}/delete",
            follow_redirects=True,
        )
        self.assertIn(b"has booking history", room_response.data)
        hostel_response = self.post(
            f"/manager/hostel/{room['hostel_id']}/delete",
            follow_redirects=True,
        )
        self.assertIn(b"has booking history", hostel_response.data)

        with self.client.session_transaction() as session:
            session["user_id"] = admin["id"]
        admin_response = self.post(
            f"/admin/hostel/{room['hostel_id']}/remove",
            follow_redirects=True,
        )
        self.assertIn(b"has booking history", admin_response.data)

        db = get_db()
        booking = db.execute(
            "SELECT booking_reference FROM bookings WHERE booking_reference=?",
            (reference,),
        ).fetchone()
        room_exists = db.execute(
            "SELECT 1 FROM rooms WHERE id=?",
            (room["id"],),
        ).fetchone()
        hostel_exists = db.execute(
            "SELECT 1 FROM hostels WHERE id=?",
            (room["hostel_id"],),
        ).fetchone()
        db.close()
        self.assertIsNotNone(booking)
        self.assertIsNotNone(room_exists)
        self.assertIsNotNone(hostel_exists)

    def test_home_page_combined_room_type_and_price_filters(self):
        response = self.client.get('/?room_type=Single&max_price=800')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'Sunrise Hostel', response.data)

    def test_room_type_price_filter_applies_to_selected_room_type(self):
        response = self.client.get('/?room_type=Single&max_price=700')
        self.assertEqual(response.status_code, 200)
        self.assertNotIn(b'Sunrise Hostel', response.data)

    def test_home_page_handles_invalid_numeric_filters(self):
        response = self.client.get('/?room_type=Single&min_price=abc&max_price=xyz')
        self.assertEqual(response.status_code, 200)
        self.assertIn(b'HostelConnect', response.data)

    def test_remote_listing_images_keep_online_url_and_offline_fallback(self):
        with app.test_request_context():
            self.assertEqual(media_url("https://example.com/hostel.jpg"), "https://example.com/hostel.jpg")
            self.assertEqual(media_url(None), "/static/offline-cover.svg")

        page = self.client.get("/")
        self.assertIn(b"OFFLINE_COVER_URL", page.data)
        self.assertIn(b"document.addEventListener", page.data)

        with self.client.get("/static/offline-cover.svg") as response:
            self.assertEqual(response.status_code, 200)
            self.assertIn(b"<svg", response.data)

    def test_booking_rejects_invalid_room_count(self):
        response = self.post(
            '/book/1',
            data={
                'full_name': 'Ada Doe',
                'phone': '0240000000',
                'email': 'ada@example.com',
                'move_in_date': (date.today() + timedelta(days=14)).isoformat(),
                'payment_period': 'semester',
                'rooms_requested': 'invalid',
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b"Enter valid booking details", response.data)
        db = get_db()
        booking = db.execute(
            "SELECT 1 FROM bookings WHERE student_email=?",
            ("ada@example.com",),
        ).fetchone()
        db.close()
        self.assertIsNone(booking)

    def test_booking_rejects_past_move_in_date(self):
        response = self.post(
            "/book/1",
            data={
                "full_name": "Ada Doe",
                "phone": "0240000000",
                "email": "past-date@example.com",
                "move_in_date": (date.today() - timedelta(days=1)).isoformat(),
                "payment_period": "semester",
                "rooms_requested": "1",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"choose a future move-in date", response.data)
        db = get_db()
        booking = db.execute(
            "SELECT 1 FROM bookings WHERE student_email=?",
            ("past-date@example.com",),
        ).fetchone()
        db.close()
        self.assertIsNone(booking)

    def test_booking_rejects_noncanonical_move_in_date(self):
        response = self.post(
            "/book/1",
            data={
                "full_name": "Ada Doe",
                "phone": "0240000000",
                "email": "invalid-date@example.com",
                "move_in_date": "20261115",
                "payment_period": "semester",
                "rooms_requested": "1",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"choose a future move-in date", response.data)

    def test_registration_rejects_short_password(self):
        response = self.post(
            "/register",
            data={
                "full_name": "New Manager",
                "email": "new-manager@example.com",
                "password": "short",
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"at least 8 characters", response.data)
        db = get_db()
        user = db.execute(
            "SELECT 1 FROM users WHERE email=?",
            ("new-manager@example.com",),
        ).fetchone()
        db.close()
        self.assertIsNone(user)

    def test_booking_rejects_room_count_above_available_inventory(self):
        db = get_db()
        room = db.execute(
            """SELECT r.id, r.available_rooms FROM rooms r
               WHERE r.available_rooms > 0 ORDER BY r.available_rooms LIMIT 1"""
        ).fetchone()
        available_rooms = room["available_rooms"]
        room_id = room["id"]
        db.close()

        response = self.post(
            f"/book/{room_id}",
            data={
                "full_name": "Avery Student",
                "phone": "0240000000",
                "email": "inventory-check@example.com",
                "move_in_date": (date.today() + timedelta(days=14)).isoformat(),
                "payment_period": "semester",
                "rooms_requested": str(available_rooms + 1),
            },
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn(b"requested number of rooms is no longer available", response.data)
        db = get_db()
        booking = db.execute(
            "SELECT 1 FROM bookings WHERE student_email=?",
            ("inventory-check@example.com",),
        ).fetchone()
        db.close()
        self.assertIsNone(booking)

    def test_manager_dashboard_counts_views_once_per_hostel(self):
        db = get_db()
        manager = db.execute(
            "SELECT id FROM users WHERE email='manager@hostelconnect.local'"
        ).fetchone()
        manager_id = manager["id"]
        before = db.execute(
            """SELECT COUNT(*) listings, COALESCE(SUM(view_count), 0) views
               FROM hostels WHERE manager_id=?""",
            (manager_id,),
        ).fetchone()
        room_totals = db.execute(
            """SELECT COALESCE(SUM(r.total_rooms), 0) total,
                      COALESCE(SUM(r.available_rooms), 0) available,
                      COALESCE(SUM(r.occupied_rooms), 0) occupied
               FROM rooms r JOIN hostels h ON h.id=r.hostel_id
               WHERE h.manager_id=?""",
            (manager_id,),
        ).fetchone()
        cursor = db.execute(
            """INSERT INTO hostels(manager_id, name, region, city, created_at, view_count)
               VALUES(?, 'Stats Regression Hostel', 'Ashanti Region', 'Kumasi', ?, 17)""",
            (manager_id, app_module.now()),
        )
        hostel_id = cursor.lastrowid
        db.executemany(
            """INSERT INTO rooms(hostel_id, room_type, price, total_rooms,
                                 available_rooms, occupied_rooms)
               VALUES(?, ?, 500, ?, ?, ?)""",
            [
                (hostel_id, "Single", 3, 2, 1),
                (hostel_id, "Shared", 2, 1, 1),
            ],
        )
        db.commit()
        db.close()

        with self.client.session_transaction() as session:
            session["user_id"] = manager_id
        response = self.client.get("/manager")

        self.assertEqual(response.status_code, 200)
        expected_stats = {
            "Listings": before["listings"] + 1,
            "Total rooms": room_totals["total"] + 5,
            "Available": room_totals["available"] + 3,
            "Occupied": room_totals["occupied"] + 2,
            "Views": before["views"] + 17,
        }
        for label, value in expected_stats.items():
            self.assertIn(
                f"<strong>{value}</strong><span>{label}</span>".encode(),
                response.data,
            )

    def test_manager_post_with_invalid_price_does_not_create_listing(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 2

        response = self.post(
            '/manager/hostel/new',
            data={
                'name': 'New Test Hostel',
                'city': 'Accra',
                'room_type': 'Single',
                'price': 'invalid',
                'total_rooms': '3',
                'available_rooms': '2',
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 400)
        self.assertIn(b'Enter a valid non-negative room price and inventory.', response.data)
        self.assertIn(b'value="invalid"', response.data)
        db = get_db()
        hostel = db.execute(
            "SELECT 1 FROM hostels WHERE name='New Test Hostel'"
        ).fetchone()
        db.close()
        self.assertIsNone(hostel)

    def test_manager_can_accept_booking_and_see_student_details(self):
        db = get_db()
        manager = db.execute(
            "SELECT id FROM users WHERE email='manager@hostelconnect.local'"
        ).fetchone()
        student = db.execute(
            "SELECT id FROM users WHERE email='student@hostelconnect.local'"
        ).fetchone()
        room = db.execute(
            """SELECT r.id, r.available_rooms, r.occupied_rooms
               FROM rooms r JOIN hostels h ON h.id=r.hostel_id
               WHERE h.manager_id=? AND r.available_rooms > 0
               ORDER BY r.id LIMIT 1""",
            (manager['id'],),
        ).fetchone()
        room_id = room['id']
        original_available = room['available_rooms']
        original_occupied = room['occupied_rooms']
        db.close()

        with self.client.session_transaction() as session:
            session['user_id'] = student['id']
        booking_response = self.post(
            f'/book/{room_id}',
            data={
                'full_name': 'Avery Booking Student',
                'phone': '0241234567',
                'email': 'avery@example.com',
                'move_in_date': (date.today() + timedelta(days=14)).isoformat(),
                'payment_period': 'semester',
                'rooms_requested': '1',
                'message': 'Please contact me about move-in.',
            },
            follow_redirects=False,
        )
        self.assertEqual(booking_response.status_code, 302)
        booking_reference = booking_response.headers['Location'].rsplit('/', 1)[-1]
        db = get_db()
        booking = db.execute(
            "SELECT id FROM bookings WHERE booking_reference=?",
            (booking_reference,),
        ).fetchone()
        booking_id = booking['id']
        db.close()

        try:
            with self.client.session_transaction() as session:
                session['user_id'] = student['id']

            pending_response = self.client.get('/dashboard')
            self.assertEqual(pending_response.status_code, 200)
            self.assertIn(b'PENDING', pending_response.data)
            self.assertIn(b'waiting for the hostel manager', pending_response.data)

            with self.client.session_transaction() as session:
                session['user_id'] = manager['id']

            response = self.post(
                f'/manager/booking/{booking_id}/accept',
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Booking request accepted.', response.data)
            self.assertIn(b'Avery Booking Student', response.data)
            self.assertIn(b'0241234567', response.data)
            self.assertIn(b'avery@example.com', response.data)
            self.assertIn(b'APPROVED', response.data)

            db = get_db()
            accepted_booking = db.execute(
                "SELECT status FROM bookings WHERE id=?",
                (booking_id,),
            ).fetchone()
            updated_room = db.execute(
                "SELECT available_rooms, occupied_rooms FROM rooms WHERE id=?",
                (room_id,),
            ).fetchone()
            db.close()
            self.assertEqual(accepted_booking['status'], 'approved')
            self.assertEqual(updated_room['available_rooms'], original_available - 1)
            self.assertEqual(updated_room['occupied_rooms'], original_occupied + 1)

            with self.client.session_transaction() as session:
                session['user_id'] = student['id']
            student_dashboard = self.client.get('/dashboard')
            self.assertEqual(student_dashboard.status_code, 200)
            self.assertIn(b'ACCEPTED', student_dashboard.data)
            self.assertIn(b'booking has been accepted', student_dashboard.data)
            self.assertIn(booking_reference.encode(), student_dashboard.data)
        finally:
            db = get_db()
            db.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
            db.execute(
                "UPDATE rooms SET available_rooms=?, occupied_rooms=? WHERE id=?",
                (original_available, original_occupied, room_id),
            )
            db.commit()
            db.close()

    def test_manager_can_reject_booking_request(self):
        db = get_db()
        manager = db.execute(
            "SELECT id FROM users WHERE email='manager@hostelconnect.local'"
        ).fetchone()
        student = db.execute(
            "SELECT id FROM users WHERE email='student@hostelconnect.local'"
        ).fetchone()
        room = db.execute(
            """SELECT r.id FROM rooms r JOIN hostels h ON h.id=r.hostel_id
               WHERE h.manager_id=? AND r.available_rooms > 0
               ORDER BY r.id LIMIT 1""",
            (manager['id'],),
        ).fetchone()
        db.close()

        with self.client.session_transaction() as session:
            session['user_id'] = student['id']
        booking_response = self.post(
            f'/book/{room["id"]}',
            data={
                'full_name': 'Jordan Booking Student',
                'phone': '0247654321',
                'email': 'jordan@example.com',
                'move_in_date': (date.today() + timedelta(days=14)).isoformat(),
                'payment_period': 'semester',
                'rooms_requested': '1',
            },
            follow_redirects=False,
        )
        booking_reference = booking_response.headers['Location'].rsplit('/', 1)[-1]
        db = get_db()
        booking = db.execute(
            "SELECT id FROM bookings WHERE booking_reference=?",
            (booking_reference,),
        ).fetchone()
        booking_id = booking['id']
        db.close()

        try:
            with self.client.session_transaction() as session:
                session['user_id'] = manager['id']

            response = self.post(
                f'/manager/booking/{booking_id}/reject',
                follow_redirects=True,
            )
            self.assertEqual(response.status_code, 200)
            self.assertIn(b'Booking request rejected.', response.data)
            self.assertIn(b'REJECTED', response.data)
            db = get_db()
            rejected_booking = db.execute(
                "SELECT status FROM bookings WHERE id=?",
                (booking_id,),
            ).fetchone()
            db.close()
            self.assertEqual(rejected_booking['status'], 'rejected')

            with self.client.session_transaction() as session:
                session['user_id'] = student['id']
            student_dashboard = self.client.get('/dashboard')
            self.assertEqual(student_dashboard.status_code, 200)
            self.assertIn(b'DECLINED', student_dashboard.data)
            self.assertIn(b'booking request', student_dashboard.data)
        finally:
            db = get_db()
            db.execute("DELETE FROM bookings WHERE id=?", (booking_id,))
            db.commit()
            db.close()

    def test_database_initialization_preserves_rooms_and_moderation(self):
        original_db_path = app_module.DB_PATH
        with tempfile.TemporaryDirectory() as directory:
            app_module.DB_PATH = Path(directory) / "accommodation.db"
            try:
                app_module.init_db()
                db = get_db()
                hostel = db.execute(
                    "SELECT id FROM hostels WHERE name='Sunrise Hostel'"
                ).fetchone()
                room = db.execute(
                    """SELECT id, hostel_id FROM rooms
                       WHERE hostel_id=? AND total_rooms > available_rooms
                       ORDER BY id LIMIT 1""",
                    (hostel["id"],),
                ).fetchone()
                student = db.execute(
                    "SELECT id FROM users WHERE email='student@hostelconnect.local'"
                ).fetchone()
                room_ids = [
                    row["id"]
                    for row in db.execute(
                        "SELECT id FROM rooms WHERE hostel_id=? ORDER BY id",
                        (hostel["id"],),
                    ).fetchall()
                ]
                db.execute(
                    "UPDATE hostels SET approval_status='rejected', verified=0 WHERE id=?",
                    (hostel["id"],),
                )
                db.execute("UPDATE rooms SET occupied_rooms=0 WHERE id=?", (room["id"],))
                db.execute(
                    """INSERT INTO bookings(
                           room_id, hostel_id, student_id, booking_reference, payment_reference,
                           amount, status, created_at
                       ) VALUES(?,?,?,?,?,?, 'pending', ?)""",
                    (
                        room["id"],
                        room["hostel_id"],
                        student["id"],
                        "SH-2026-0001",
                        "SH-2026-0001",
                        800,
                        app_module.now(),
                    ),
                )
                db.commit()
                db.close()

                app_module.init_db()

                db = get_db()
                hostel = db.execute(
                    "SELECT approval_status, verified FROM hostels WHERE name='Sunrise Hostel'"
                ).fetchone()
                actual_room_ids = [
                    row["id"]
                    for row in db.execute(
                        "SELECT id FROM rooms WHERE hostel_id=? ORDER BY id",
                        (room["hostel_id"],),
                    ).fetchall()
                ]
                booking = db.execute(
                    """SELECT booking_reference, payment_reference FROM bookings
                       WHERE student_id=? AND amount=800""",
                    (student["id"],),
                ).fetchone()
                occupied_rooms = db.execute(
                    "SELECT occupied_rooms FROM rooms WHERE id=?", (room["id"],)
                ).fetchone()["occupied_rooms"]
                db.close()

                self.assertEqual(hostel["approval_status"], "rejected")
                self.assertEqual(hostel["verified"], 0)
                self.assertEqual(actual_room_ids, room_ids)
                self.assertIsNotNone(booking)
                self.assertRegex(
                    booking["booking_reference"],
                    r"^[A-Z]{2}-\d{4}-R[0-9a-f]{32}$",
                )
                self.assertEqual(booking["payment_reference"], booking["booking_reference"])
                self.assertEqual(occupied_rooms, 0)
                migrated_reference = booking["booking_reference"]
                app_module.init_db()
                db = get_db()
                persisted_reference = db.execute(
                    """SELECT booking_reference FROM bookings
                       WHERE student_id=? AND amount=800""",
                    (student["id"],),
                ).fetchone()["booking_reference"]
                db.close()
                self.assertEqual(persisted_reference, migrated_reference)
            finally:
                app_module.DB_PATH = original_db_path


if __name__ == '__main__':
    unittest.main()
