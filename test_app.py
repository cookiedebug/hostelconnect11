import tempfile
import unittest
from pathlib import Path

import app as app_module
from app import app, get_db
from app import media_url


class AccommodationFilterTests(unittest.TestCase):
    def setUp(self):
        self.client = app.test_client()

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

    def test_booking_invalid_room_count_does_not_crash(self):
        response = self.client.post(
            '/book/1',
            data={
                'full_name': 'Ada Doe',
                'phone': '0240000000',
                'email': 'ada@example.com',
                'move_in_date': '2026-01-15',
                'payment_period': 'semester',
                'rooms_requested': 'invalid',
            },
            follow_redirects=False,
        )
        self.assertEqual(response.status_code, 302)
        self.assertIn('/booking/confirmation/', response.headers.get('Location', ''))

    def test_manager_post_with_invalid_price_still_redirects(self):
        with self.client.session_transaction() as session:
            session['user_id'] = 2

        response = self.client.post(
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
        self.assertEqual(response.status_code, 302)

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
        booking_response = self.client.post(
            f'/book/{room_id}',
            data={
                'full_name': 'Avery Booking Student',
                'phone': '0241234567',
                'email': 'avery@example.com',
                'move_in_date': '2026-11-01',
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

            response = self.client.post(
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
        booking_response = self.client.post(
            f'/book/{room["id"]}',
            data={
                'full_name': 'Jordan Booking Student',
                'phone': '0247654321',
                'email': 'jordan@example.com',
                'move_in_date': '2026-11-02',
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

            response = self.client.post(
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
                           room_id, hostel_id, student_id, booking_reference, amount, status, created_at
                       ) VALUES(?,?,?,?,?,'pending',?)""",
                    (
                        room["id"],
                        room["hostel_id"],
                        student["id"],
                        "TEST-DB-INIT-001",
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
                    "SELECT id FROM bookings WHERE booking_reference='TEST-DB-INIT-001'"
                ).fetchone()
                occupied_rooms = db.execute(
                    "SELECT occupied_rooms FROM rooms WHERE id=?", (room["id"],)
                ).fetchone()["occupied_rooms"]
                db.close()

                self.assertEqual(hostel["approval_status"], "rejected")
                self.assertEqual(hostel["verified"], 0)
                self.assertEqual(actual_room_ids, room_ids)
                self.assertIsNotNone(booking)
                self.assertEqual(occupied_rooms, 0)
            finally:
                app_module.DB_PATH = original_db_path


if __name__ == '__main__':
    unittest.main()
