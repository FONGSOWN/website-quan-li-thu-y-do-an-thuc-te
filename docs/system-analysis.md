# PetCare — Phân tích hệ thống

## Vai trò và use case

| Vai trò | Chức năng chính |
|---|---|
| Khách hàng | Đăng ký, quản lý thú cưng, tiêm phòng, đặt/hủy lịch, xem hóa đơn |
| Thu ngân | Duyệt lịch, lập và in hóa đơn |
| Bác sĩ | Xem ca khám, lập bệnh án và hẹn tái khám |
| Quản trị viên | Quản lý nhân sự, dịch vụ và theo dõi thống kê |

## Kiến trúc

```mermaid
flowchart LR
Browser[Trình duyệt] --> Flask[Flask routes + RBAC]
Flask --> SQLite[(SQLite)]
Flask --> Upload[Tệp ảnh an toàn]
```

## ERD rút gọn

```mermaid
erDiagram
USERS ||--o| CUSTOMERS : owns
CUSTOMERS ||--o{ PETS : manages
PETS ||--o{ VACCINATIONS : has
CUSTOMERS ||--o{ APPOINTMENTS : books
PETS ||--o{ APPOINTMENTS : attends
USERS ||--o{ APPOINTMENTS : doctor
APPOINTMENTS ||--o| MEDICAL_RECORDS : creates
APPOINTMENTS ||--o| INVOICES : bills
INVOICES ||--o{ INVOICE_ITEMS : contains
```
