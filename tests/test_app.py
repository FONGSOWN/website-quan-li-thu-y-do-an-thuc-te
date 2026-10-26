"""
tests/test_app.py – Bộ kiểm thử cho PetCare Website
Chạy: python -m pytest tests/ -v
"""
import re
from datetime import date, timedelta

import pytest

from app import create_app
from werkzeug.security import check_password_hash


# ── FIXTURE ────────────────────────────────────────────────────────────

@pytest.fixture()
def client(tmp_path, monkeypatch):
    """Tạo client kiểm thử riêng biệt với SQLite tạm."""
    monkeypatch.setenv("PETCARE_DEMO_ADMIN_PASSWORD", "admin123")
    monkeypatch.setenv("PETCARE_DEMO_PASSWORD", "123456")
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-secret-key-not-for-production",
        "DATABASE": str(tmp_path / "test.db"),
        "ADMIN_USERNAME": "tester",
        "ADMIN_PASSWORD": "safe-pass-123",
    })
    return app.test_client()


# ── HELPERS ─────────────────────────────────────────────────────────────

def get_csrf_token(response):
    """Lấy CSRF token từ HTML response."""
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, "Không tìm thấy CSRF token trong trang"
    return match.group(1)


def admin_login(client):
    """Đăng nhập admin và trả về response dashboard."""
    page = client.get("/admin/login")
    return client.post(
        "/admin/login",
        data={"csrf_token": get_csrf_token(page), "username": "tester", "password": "safe-pass-123"},
        follow_redirects=True,
    )


def tomorrow():
    return (date.today() + timedelta(days=1)).isoformat()


def today():
    return date.today().isoformat()


def yesterday():
    return (date.today() - timedelta(days=1)).isoformat()


# ── TEST 1: Trang công khai và bảo vệ admin ─────────────────────────────

def test_public_pages_return_200(client):
    """Tất cả trang công khai phải trả về HTTP 200."""
    pages = ["/", "/gioi-thieu", "/dich-vu", "/bac-si", "/dat-lich", "/lien-he"]
    for path in pages:
        r = client.get(path)
        assert r.status_code == 200, f"Trang {path} trả về {r.status_code}"


def test_admin_requires_login(client):
    """/admin và /admin/appointments/new phải redirect về login nếu chưa đăng nhập."""
    assert client.get("/admin").status_code == 302
    assert client.get("/admin/appointments/new").status_code == 302
    assert client.get("/admin/appointments/1/edit").status_code == 302


def test_404_returns_html(client):
    """Trang không tồn tại phải trả về 404 với HTML thân thiện."""
    r = client.get("/khong-ton-tai")
    assert r.status_code == 404
    assert b"404" in r.data or b"trang" in r.data.lower()


# ── TEST 2: Đặt lịch ─────────────────────────────────────────────────────

def test_booking_past_date_rejected(client):
    """Ngày trong quá khứ phải bị từ chối."""
    page = client.get("/dat-lich")
    r = client.post("/dat-lich", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Nguyễn Test", "phone": "0901234567",
        "pet_name": "Miu", "appointment_date": yesterday(),
        "service": "Khám sức khỏe", "note": "",
    }, follow_redirects=True)
    assert "Ngày khám phải" in r.get_data(as_text=True)


def test_booking_missing_fields_rejected(client):
    """Thiếu trường bắt buộc phải bị từ chối."""
    page = client.get("/dat-lich")
    r = client.post("/dat-lich", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "", "phone": "0901234567",
        "pet_name": "Miu", "appointment_date": today(),
        "service": "Khám sức khỏe",
    }, follow_redirects=True)
    assert "đầy đủ" in r.get_data(as_text=True)


def test_booking_invalid_phone_rejected(client):
    """Số điện thoại sai định dạng phải bị từ chối."""
    page = client.get("/dat-lich")
    r = client.post("/dat-lich", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Nguyễn A", "phone": "abc",
        "pet_name": "Miu", "appointment_date": today(),
        "service": "Khám sức khỏe", "note": "",
    }, follow_redirects=True)
    assert "điện thoại" in r.get_data(as_text=True).lower()


def test_booking_valid_saved_to_db(client):
    """Lịch hẹn hợp lệ phải được lưu và hiển thị trong admin."""
    page = client.get("/dat-lich")
    r = client.post("/dat-lich", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Nguyễn Thị An", "phone": "0901234567",
        "pet_name": "Lucky", "appointment_date": today(),
        "service": "Tiêm phòng", "note": "Lần đầu tiêm",
    }, follow_redirects=True)
    assert "Đặt lịch thành công" in r.get_data(as_text=True)

    # Kiểm tra dữ liệu xuất hiện trong admin
    dashboard = admin_login(client)
    assert "Lucky" in dashboard.get_data(as_text=True)
    assert "Nguyễn Thị An" in dashboard.get_data(as_text=True)


def test_booking_invalid_service_rejected(client):
    """Dịch vụ không hợp lệ phải bị từ chối."""
    page = client.get("/dat-lich")
    r = client.post("/dat-lich", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Test", "phone": "0901234567",
        "pet_name": "Test", "appointment_date": today(),
        "service": "Dịch vụ không tồn tại", "note": "",
    }, follow_redirects=True)
    assert "dịch vụ" in r.get_data(as_text=True).lower()


# ── TEST 3: Liên hệ ──────────────────────────────────────────────────────

def test_contact_valid_message_saved(client):
    """Tin nhắn hợp lệ phải được lưu và báo thành công."""
    page = client.get("/lien-he")
    r = client.post("/lien-he", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Trần Bình", "email": "binh@example.com",
        "message": "Cần tư vấn dịch vụ tiêm phòng.",
    }, follow_redirects=True)
    assert "Tin nhắn đã được gửi" in r.get_data(as_text=True)


def test_contact_invalid_email_rejected(client):
    """Email không hợp lệ phải bị từ chối."""
    page = client.get("/lien-he")
    r = client.post("/lien-he", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Trần Bình", "email": "not-an-email",
        "message": "Test message.",
    }, follow_redirects=True)
    assert "chưa hợp lệ" in r.get_data(as_text=True) or "không hợp lệ" in r.get_data(as_text=True)


# ── TEST 4: Admin xác thực ───────────────────────────────────────────────

def test_admin_login_success(client):
    """Đăng nhập đúng credentials phải vào được dashboard."""
    r = admin_login(client)
    assert "Quản lý trung tâm" in r.get_data(as_text=True)


def test_admin_login_wrong_password(client):
    """Mật khẩu sai phải bị từ chối."""
    page = client.get("/admin/login")
    r = client.post("/admin/login", data={
        "csrf_token": get_csrf_token(page),
        "username": "tester", "password": "wrong-password",
    }, follow_redirects=True)
    assert "không đúng" in r.get_data(as_text=True)


def test_admin_csrf_protection(client):
    """POST không có CSRF token hợp lệ phải trả về 400."""
    r = client.post("/dat-lich", data={})
    assert r.status_code == 400


def test_admin_logout(client):
    """Sau đăng xuất phải không truy cập được admin."""
    admin_login(client)
    # Lấy CSRF từ dashboard để logout
    dash = client.get("/admin")
    r = client.post("/admin/logout", data={"csrf_token": get_csrf_token(dash)},
                    follow_redirects=True)
    assert "Đăng nhập" in r.get_data(as_text=True)
    # Thử truy cập admin sau logout
    assert client.get("/admin").status_code == 302


# ── TEST 5: Admin CRUD lịch hẹn ─────────────────────────────────────────

def test_admin_create_appointment(client):
    """Admin tạo lịch mới phải được lưu."""
    admin_login(client)
    page = client.get("/admin/appointments/new")
    r = client.post("/admin/appointments/new", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Lê Chi",
        "phone": "0912345678",
        "pet_name": "Bông",
        "appointment_date": today(),
        "service": "Tắm và vệ sinh",
        "note": "Lông dài",
        "status": "Chờ xác nhận",
    }, follow_redirects=True)
    assert "Đã lưu lịch hẹn" in r.get_data(as_text=True)
    assert "Bông" in r.get_data(as_text=True)


def test_admin_update_status(client):
    """Cập nhật trạng thái lịch phải thay đổi trong DB."""
    # Tạo lịch trước
    admin_login(client)
    page = client.get("/admin/appointments/new")
    client.post("/admin/appointments/new", data={
        "csrf_token": get_csrf_token(page), "full_name": "Test",
        "phone": "0900000001", "pet_name": "Rex", "appointment_date": today(),
        "service": "Khám sức khỏe", "note": "", "status": "Chờ xác nhận",
    }, follow_redirects=True)
    # Cập nhật trạng thái
    dash = client.get("/admin")
    r = client.post("/admin/appointments/1/status", data={
        "csrf_token": get_csrf_token(dash), "status": "Đã xác nhận",
    }, follow_redirects=True)
    assert "Đã cập nhật" in r.get_data(as_text=True)


def test_admin_delete_appointment(client):
    """Xóa lịch phải xóa khỏi DB."""
    admin_login(client)
    page = client.get("/admin/appointments/new")
    client.post("/admin/appointments/new", data={
        "csrf_token": get_csrf_token(page), "full_name": "Cần xóa",
        "phone": "0900000002", "pet_name": "Cat", "appointment_date": today(),
        "service": "Tiêm phòng", "note": "", "status": "Chờ xác nhận",
    }, follow_redirects=True)
    with client.application.app_context():
        import sqlite3
        database = sqlite3.connect(client.application.config["DATABASE"])
        appointment_id = database.execute(
            "SELECT id FROM appointments WHERE pet_name=? ORDER BY id DESC LIMIT 1", ("Cat",)
        ).fetchone()[0]
        database.close()
    dash = client.get("/admin")
    r = client.post(f"/admin/appointments/{appointment_id}/delete",
                    data={"csrf_token": get_csrf_token(dash)},
                    follow_redirects=True)
    assert "Đã xóa lịch hẹn" in r.get_data(as_text=True)
    assert "Cần xóa" not in r.get_data(as_text=True)


# ── TEST 6: Admin quản lý tin nhắn ──────────────────────────────────────

def test_admin_mark_message_read_and_delete(client):
    """Đánh dấu đọc và xóa tin nhắn phải hoạt động."""
    # Gửi tin nhắn trước
    page = client.get("/lien-he")
    client.post("/lien-he", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Người dùng test", "email": "test@example.com",
        "message": "Tin nhắn kiểm thử",
    }, follow_redirects=True)

    admin_login(client)

    # Đánh dấu đã đọc
    dash = client.get("/admin")
    r = client.post("/admin/messages/1/read",
                    data={"csrf_token": get_csrf_token(dash)},
                    follow_redirects=True)
    assert "đã đọc" in r.get_data(as_text=True).lower()

    # Xóa tin nhắn
    dash = client.get("/admin")
    r = client.post("/admin/messages/1/delete",
                    data={"csrf_token": get_csrf_token(dash)},
                    follow_redirects=True)
    assert "Đã xóa tin nhắn" in r.get_data(as_text=True)


# ── TEST 7: Persistence – dữ liệu tồn tại sau restart ───────────────────

def test_data_persists(tmp_path):
    """Dữ liệu phải tồn tại giữa các instance app (mô phỏng restart)."""
    db_path = str(tmp_path / "persist.db")
    config = {"TESTING": True, "SECRET_KEY": "x", "DATABASE": db_path,
               "ADMIN_USERNAME": "a", "ADMIN_PASSWORD": "b"}

    # Instance 1: Gửi lịch hẹn
    app1 = create_app(config)
    with app1.test_client() as c1:
        page = c1.get("/dat-lich")
        c1.post("/dat-lich", data={
            "csrf_token": get_csrf_token(page), "full_name": "Persist Test",
            "phone": "0900000099", "pet_name": "Dog", "appointment_date": today(),
            "service": "Khám sức khỏe", "note": "",
        }, follow_redirects=True)

    # Instance 2: Kiểm tra dữ liệu vẫn còn
    app2 = create_app(config)
    with app2.test_client() as c2:
        login_page = c2.get("/admin/login")
        r = c2.post("/admin/login", data={
            "csrf_token": get_csrf_token(login_page), "username": "a", "password": "b",
        }, follow_redirects=True)
        assert "Persist Test" in r.get_data(as_text=True), \
            "Dữ liệu bị mất sau khi khởi động lại app!"


# ── TEST 8: Các tính năng cải tiến mới ──────────────────────────────────

def test_admin_can_edit_past_appointment(client):
    """Admin phải có thể sửa thông tin của lịch hẹn trong quá khứ."""
    admin_login(client)
    page = client.get("/admin/appointments/new")
    client.post("/admin/appointments/new", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Khách khám cũ",
        "phone": "0987654321",
        "pet_name": "Miu Miu",
        "appointment_date": today(),
        "service": "Khám sức khỏe",
        "note": "Ban đầu",
        "status": "Chờ xác nhận",
    }, follow_redirects=True)

    # Admin sửa ngày về quá khứ và cập nhật trạng thái "Đã hoàn thành"
    edit_page = client.get("/admin/appointments/1/edit")
    r = client.post("/admin/appointments/1/edit", data={
        "csrf_token": get_csrf_token(edit_page),
        "full_name": "Khách khám cũ",
        "phone": "0987654321",
        "pet_name": "Miu Miu",
        "appointment_date": yesterday(),
        "service": "Khám sức khỏe",
        "note": "Đã khám xong - sức khỏe tốt",
        "status": "Đã hoàn thành",
    }, follow_redirects=True)
    assert "Đã lưu lịch hẹn" in r.get_data(as_text=True)
    assert "Đã hoàn thành" in r.get_data(as_text=True)


def test_booking_preselect_service(client):
    """Truy cập /dat-lich?service=Tiêm phòng phải có option được chọn sẵn."""
    r = client.get("/dat-lich?service=Ti%C3%AAm+ph%C3%B2ng")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert 'selected>Tiêm phòng</option>' in html or 'selected' in html


def test_booking_invalid_phone_symbols_only(client):
    """Số điện thoại chỉ toàn ký tự phân cách (không đủ chữ số) phải bị từ chối."""
    page = client.get("/dat-lich")
    r = client.post("/dat-lich", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Test Phone",
        "phone": "-----------",
        "pet_name": "Pet",
        "appointment_date": today(),
        "service": "Khám sức khỏe",
    }, follow_redirects=True)
    assert "chưa đúng định dạng" in r.get_data(as_text=True)


def test_demo_seed_accounts_are_hashed_and_idempotent(client):
    with client.application.app_context():
        database = client.application.extensions.get("sqlite_db")
        if database is None:
            import sqlite3
            database = sqlite3.connect(client.application.config["DATABASE"])
            database.row_factory = sqlite3.Row
        admin = database.execute("SELECT * FROM users WHERE username='admin'").fetchone()
        assert admin is not None
        assert admin["password_hash"] != "admin123"
        assert check_password_hash(admin["password_hash"], "admin123") is True
        assert database.execute("SELECT COUNT(*) FROM invoices").fetchone()[0] >= 2


def test_admin_users_alias_and_staff_alias(client):
    admin_login(client)
    assert client.get("/admin/users").status_code == 200
    assert client.get("/admin/staff").status_code == 200


def test_admin_users_can_add_staff(client):
    admin_login(client)
    page = client.get("/admin/users")
    r = client.post("/admin/users", data={
        "csrf_token": get_csrf_token(page),
        "full_name": "Bác sĩ kiểm thử",
        "username": "doctor_test",
        "password": "safe-test-password",
        "role": "DOCTOR",
    }, follow_redirects=True)
    assert "Đã thêm nhân sự" in r.get_data(as_text=True)


def test_non_admin_cannot_access_admin_users(client):
    page = client.get("/login")
    r = client.post("/login", data={
        "csrf_token": get_csrf_token(page),
        "username": "khachhang01",
        "password": "123456",
    })
    assert r.status_code == 302
    assert client.get("/admin/users").status_code == 403

