"""
tests/test_doctor_portal.py – Kiểm thử Cổng Bác sĩ & Xác thực Phân quyền
Chạy: python -m pytest tests/test_doctor_portal.py -v
"""
import re
from datetime import date, timedelta
import pytest
from app import create_app


@pytest.fixture()
def client(tmp_path):
    app = create_app({
        "TESTING": True,
        "SECRET_KEY": "test-doctor-key",
        "DATABASE": str(tmp_path / "test_doc.db"),
        "ADMIN_USERNAME": "admin_test",
        "ADMIN_PASSWORD": "admin_test_pass",
        "DOCTOR_DEFAULT_PASSWORD": "Doctor@123",
    })
    return app.test_client()


def get_csrf(response):
    match = re.search(r'name="csrf_token" value="([^"]+)"', response.get_data(as_text=True))
    assert match, "Không tìm thấy CSRF token trong phản hồi HTML"
    return match.group(1)


def doctor_login(client, username="doctor_minh_anh", password="Doctor@123"):
    page = client.get("/login")
    return client.post("/login", data={
        "csrf_token": get_csrf(page),
        "username": username,
        "password": password
    }, follow_redirects=True)


def test_doctor_login_success(client):
    """Bác sĩ đăng nhập thành công và chuyển hướng đến trang doctor dashboard."""
    r = doctor_login(client)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "Bác sĩ" in html or "Ca khám" in html or "Dashboard Bác sĩ" in html


def test_doctor_access_pages(client):
    """Bác sĩ có thể truy cập dashboard, lịch trực và hồ sơ cá nhân."""
    doctor_login(client)

    r_dash = client.get("/doctor")
    assert r_dash.status_code == 200
    assert "Ca khám" in r_dash.get_data(as_text=True)

    r_sched = client.get("/doctor/schedules")
    assert r_sched.status_code == 200
    assert "Lịch trực" in r_sched.get_data(as_text=True)

    r_prof = client.get("/doctor/profile")
    assert r_prof.status_code == 200
    assert "Hồ sơ" in r_prof.get_data(as_text=True)


def test_doctor_update_profile(client):
    """Bác sĩ có thể cập nhật thông tin chuyên môn."""
    doctor_login(client)
    page = client.get("/doctor/profile")
    token = get_csrf(page)

    r = client.post("/doctor/profile", data={
        "csrf_token": token,
        "full_name": "BS. Nguyễn Minh Anh Cập Nhật",
        "degree": "Tiến sĩ Thú y",
        "specialty": "Ngoại khoa & Phẫu thuật Chuyên sâu",
        "phone": "0988 777 666",
        "experience_years": "9",
        "bio": "Hơn 9 năm kinh nghiệm công tác tại bệnh viện thú y quốc tế.",
        "new_password": ""
    }, follow_redirects=True)

    assert r.status_code == 200
    assert "BS. Nguyễn Minh Anh Cập Nhật" in r.get_data(as_text=True)


def test_public_doctor_detail_page(client):
    """Trang chi tiết bác sĩ công khai /bac-si/<id> hiển thị đầy đủ ảnh, họ tên, chuyên môn."""
    r = client.get("/bac-si/1")
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "BS.CKI Nguyễn Minh Anh" in html or "Nguyễn Minh Anh" in html
    assert "Kinh nghiệm" in html
    assert "Đặt lịch khám" in html


def test_rbac_doctor_cannot_access_admin(client):
    """Bác sĩ không thể truy cập các trang quản trị của Admin (403)."""
    doctor_login(client)
    r = client.get("/admin")
    assert r.status_code == 403


def test_rbac_guest_cannot_access_doctor_dashboard(client):
    """Khách chưa đăng nhập vào /doctor sẽ bị redirect về /login."""
    r = client.get("/doctor")
    assert r.status_code == 302
    assert "/login" in r.headers["Location"]


def test_api_slots_accessible_publicly(client):
    """Khách vãng lai chưa đăng nhập vẫn có thể gọi API /api/slots để xem giờ trống."""
    tomorrow = (date.today() + timedelta(days=1)).isoformat()
    r = client.get(f"/api/slots?doctor_id=1&date={tomorrow}")
    assert r.status_code == 200
    data = r.get_json()
    assert "slots" in data
    assert isinstance(data["slots"], list)

