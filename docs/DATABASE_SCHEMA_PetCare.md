# TÀI LIỆU THIẾT KẾ CƠ SỞ DỮ LIỆU (DATABASE SCHEMA)
## Hệ thống Quản lý Trung tâm Thú y — **PetCare**

> **Tài liệu:** Database Specification & Data Dictionary  
> **Hệ quản trị CSDL:** SQLite 3 (Tương thích ANSI SQL)  
> **Phiên bản:** 1.0 | **Ngày lập:** 16/11/2026

---

## 1. Sơ đồ Thực thể - Liên kết (ERD)

```mermaid
erDiagram
    USERS ||--o| CUSTOMERS : "1-1 hồ sơ khách"
    USERS ||--o{ DOCTOR_SCHEDULES : "1-N lịch trực"
    USERS ||--o{ APPOINTMENTS : "1-N bác sĩ phụ trách"
    USERS ||--o{ MEDICAL_RECORDS : "1-N bác sĩ khám"
    USERS ||--o{ NOTIFICATIONS : "1-N thông báo"

    CUSTOMERS ||--o{ PETS : "1-N nuôi thú cưng"
    CUSTOMERS ||--o{ APPOINTMENTS : "1-N đặt lịch"
    CUSTOMERS ||--o{ INVOICES : "1-N người thanh toán"

    PETS ||--o{ VACCINATIONS : "1-N mũi tiêm"
    PETS ||--o{ APPOINTMENTS : "1-N được khám"
    PETS ||--o{ MEDICAL_RECORDS : "1-N hồ sơ bệnh án"

    SERVICES ||--o{ APPOINTMENTS : "1-N loại dịch vụ"
    APPOINTMENTS ||--o| MEDICAL_RECORDS : "1-1 bệnh án"
    APPOINTMENTS ||--o| INVOICES : "1-1 hóa đơn"
    INVOICES ||--o{ INVOICE_ITEMS : "1-N chi tiết"
```

---

## 2. Danh sách 12 bảng trong CSDL

1. `users` — Người dùng hệ thống (Admin, Doctor, Cashier, Customer)
2. `customers` — Thông tin bổ sung khách hàng
3. `services` — Danh mục dịch vụ và bảng giá
4. `pets` — Hồ sơ thú cưng
5. `vaccinations` — Sổ theo dõi tiêm phòng
6. `doctor_schedules` — Lịch trực bác sĩ
7. `appointments` — Cuộc hẹn khám bệnh
8. `medical_records` — Bệnh án chi tiết
9. `invoices` — Hóa đơn thanh toán
10. `invoice_items` — Chi tiết dòng phụ phí
11. `notifications` — Thông báo nội bộ
12. `messages` — Tin nhắn liên hệ từ khách
