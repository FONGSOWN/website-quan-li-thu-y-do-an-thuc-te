"""Tạo dữ liệu minh họa độc lập; không chạy nếu chưa đặt PETCARE_DEMO_PASSWORD."""
import os

from werkzeug.security import generate_password_hash

from app import create_app


def main():
    password = os.environ.get("PETCARE_DEMO_PASSWORD")
    if not password or len(password) < 8:
        raise SystemExit("Đặt PETCARE_DEMO_PASSWORD (ít nhất 8 ký tự) trước khi chạy seed.")
    application = create_app()
    with application.app_context():
        database = application.extensions.get("sqlite_db")
        if database is None:
            import sqlite3
            database = sqlite3.connect(application.config["DATABASE"])
        accounts = (("demo_doctor", "Bác sĩ Demo", "DOCTOR"), ("demo_cashier", "Thu ngân Demo", "CASHIER"))
        for username, full_name, role in accounts:
            database.execute("INSERT OR IGNORE INTO users(username,password_hash,full_name,role) VALUES (?,?,?,?)", (username, generate_password_hash(password), full_name, role))
        database.commit()
    print("Đã tạo (hoặc giữ nguyên) tài khoản demo bác sĩ và thu ngân.")


if __name__ == "__main__":
    main()
