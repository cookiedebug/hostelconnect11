import tempfile
from pathlib import Path

import app as app_module


def main():
    original_db_path = app_module.DB_PATH
    with tempfile.TemporaryDirectory() as directory:
        app_module.DB_PATH = Path(directory) / "accommodation.db"
        try:
            app_module.init_db()
            client = app_module.app.test_client()
            csrf_token = "admin-smoke-check-token"
            with client.session_transaction() as session:
                session["_csrf_token"] = csrf_token
            login = client.post(
                "/login",
                data={
                    "_csrf_token": csrf_token,
                    "email": "admin@hostelconnect.local",
                    "password": "admin123",
                },
            )
            if login.status_code != 302:
                raise RuntimeError(f"Admin login failed with HTTP {login.status_code}.")

            dashboard = client.get("/admin")
            if dashboard.status_code != 200 or b"Platform overview" not in dashboard.data:
                raise RuntimeError("The administrator dashboard did not load.")

            hostel_form = client.get("/manager/hostel/new")
            if hostel_form.status_code != 200 or b"Add a hostel" not in hostel_form.data:
                raise RuntimeError("The administrator hostel form did not load.")

            print("Admin login, dashboard, and hostel form are working.")
        finally:
            app_module.DB_PATH = original_db_path


if __name__ == "__main__":
    main()
