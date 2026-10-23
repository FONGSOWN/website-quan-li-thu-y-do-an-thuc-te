# 🐾 PetCare — Hệ thống quản lý trung tâm thú y

Ứng dụng Flask + SQLite cho đồ án: khách hàng/thú cưng, đặt lịch, bệnh án, hóa đơn và phân quyền.

## Chạy trên Windows với VS Code

Mở `D:\WEBSITE_TRUNG_TAM_THU_Y_DO_AN`, mở Terminal PowerShell và chạy:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
Copy-Item .env.example .env
python app.py
```

Trước khi chạy, thay `PETCARE_SECRET_KEY`, `PETCARE_ADMIN_USER` và `PETCARE_ADMIN_PASSWORD` trong `.env` bằng giá trị riêng. Không commit `.env`.

Mở `http://127.0.0.1:5000`.

## Kiểm thử

```powershell
python -m pytest tests/ -v
```

Test dùng SQLite tạm thời, không tác động `instance/petcare.db`.

## An toàn dữ liệu

- Database tự thêm bảng/cột còn thiếu, không xóa dữ liệu cũ.
- Bản sao trước nâng cấp nằm trong `instance/backups/` và bị Git bỏ qua.
- Upload chỉ nhận PNG/JPG/JPEG/WEBP, tối đa 5 MB.
- Mật khẩu được hash bằng Werkzeug; mọi form POST có CSRF token.
- Nút **In / Lưu PDF** dùng hộp thoại in của trình duyệt.

## Dữ liệu demo

Không có mật khẩu demo hardcode. Đặt mật khẩu riêng trước khi chạy:

```powershell
$env:PETCARE_DEMO_PASSWORD = "mat-khau-rieng-it-nhat-8-ky-tu"
python seed_demo.py
```

Script tạo (hoặc giữ nguyên) `demo_doctor` và `demo_cashier`. Admin được tạo từ `.env` trong lần khởi động đầu tiên.

Xem [phân tích hệ thống](docs/system-analysis.md) và [kịch bản demo/test case](docs/demo-and-test-cases.md).
