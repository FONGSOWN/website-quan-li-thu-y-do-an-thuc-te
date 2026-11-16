# TÀI LIỆU PHÂN TÍCH VÀ THIẾT KẾ HỆ THỐNG (SAD)
## Hệ thống Quản lý Trung tâm Thú y — **PetCare**

> **Tài liệu:** System Architecture & Design Document (SAD)  
> **Phiên bản:** 1.0 | **Ngày lập:** 16/11/2026 | **Đối tượng:** Đồ án môn học / Báo cáo kỹ thuật  
> **Dự án:** PetCare Web Application (Flask + SQLite)

---

## 1. Giới thiệu & Mục tiêu thiết kế

### 1.1 Mục đích tài liệu
Tài liệu này đặc tả chi tiết kiến trúc phần mềm, các mô hình phân tích (Use Case, Activity, Sequence, State), thiết kế thành phần logic và kiến trúc an toàn dữ liệu cho hệ thống **PetCare**. Tài liệu đóng vai trò kim chỉ nam kỹ thuật cho nhóm phát triển và tài liệu thẩm định cho hội đồng chấm đồ án.

### 1.2 Mục tiêu thiết kế (Architectural Goals)
- **Đơn giản & Dễ vận hành:** Sử dụng kiến trúc Client-Server với Flask (Python) và SQLite, không cần cấu hình server phức tạp, tự migrate dữ liệu khi khởi động.
- **Tính toàn vẹn & Tin cậy dữ liệu:** Kiểm soát xung đột lịch hẹn bằng SQLite Partial Unique Index; đảm bảo khóa ngoại và ràng buộc cascade.
- **Bảo mật nhiều lớp:** Xác thực Cookie Session an toàn, kiểm soát quyền theo vai trò (RBAC), phòng chống CSRF bắt buộc trên toàn bộ form POST, mã hóa mật khẩu PBKDF2, kiểm tra whitelist và kích thước file upload (5 MB).

---

## 2. Kiến trúc hệ thống tổng thể

```mermaid
flowchart TD
    subgraph ClientLayer["1. Presentation Layer (Trình duyệt)"]
        HTML["Jinja2 HTML Templates"]
        CSS["Modern CSS (Responsive, Print stylesheet)"]
        JS["Vanilla JS (Slot Picker Fetch API, Form Validation)"]
    end

    subgraph AppLayer["2. Application / Business Logic Layer (Flask Core)"]
        Router["Flask Routing & Context Processor"]
        SecurityMW["Security Middleware (CSRF, Session, RBAC Guards)"]
        ServiceLogic["Business Controller (Auth, Booking, Exam, Invoice, Admin)"]
        StorageEngine["Media File Storage Handler (Uploads, Whitelist, Sanitize)"]
    end

    subgraph DataLayer["3. Data Persistence Layer (Cơ sở dữ liệu)"]
        SQLiteEngine["SQLite Database (instance/petcare.db)"]
        ForeignKeys["Foreign Keys + Cascade Rules"]
        Indexes["Unique Index (Slot Conflict Prevention)"]
    end

    ClientLayer --> Router
    Router --> SecurityMW
    SecurityMW --> ServiceLogic
    ServiceLogic --> SQLiteEngine
    ServiceLogic --> StorageEngine
    SQLiteEngine --> ForeignKeys
    SQLiteEngine --> Indexes
    ServiceLogic --> HTML
    HTML --> ClientLayer
```

---

## 3. Phân tích Use Case chi tiết

```mermaid
flowchart LR
    Customer((Khách hàng))
    Doctor((Bác sĩ))
    Cashier((Thu ngân))
    Admin((Quản trị viên))

    subgraph UC_Customer["Nghiệp vụ Khách hàng"]
        UC01[Đăng ký / Đăng nhập]
        UC02[Quản lý hồ sơ thú cưng]
        UC03[Xem sổ tiêm phòng]
        UC04[Đặt lịch khám trực tuyến]
        UC05[Hủy lịch hẹn]
        UC06[Xem lịch sử khám & Hóa đơn]
    end

    subgraph UC_Doctor["Nghiệp vụ Bác sĩ"]
        UC07[Xem ca khám & Lịch trực]
        UC08[Khám bệnh & Lập bệnh án]
        UC09[Kê đơn thuốc & Hẹn tái khám]
        UC10[Đính kèm file kết quả xét nghiệm]
    end

    subgraph UC_Cashier["Nghiệp vụ Thu ngân"]
        UC11[Tiếp nhận & Duyệt lịch hẹn]
        UC12[Lập hóa đơn thanh toán]
        UC13[In phiếu thu / hóa đơn PDF]
    end

    subgraph UC_Admin["Quản trị hệ thống"]
        UC14[Quản lý tài khoản nhân sự]
        UC15[Phân ca trực bác sĩ]
        UC16[Quản lý danh mục dịch vụ]
        UC17[Xem báo cáo & Doanh thu]
    end

    Customer --> UC01 & UC02 & UC03 & UC04 & UC05 & UC06
    Doctor --> UC01 & UC07 & UC08 & UC09 & UC10
    Cashier --> UC01 & UC11 & UC12 & UC13
    Admin --> UC01 & UC14 & UC15 & UC16 & UC17
```

---

## 4. Biểu đồ tuần tự (Sequence Diagram)

### Đặt lịch khám và Kiểm tra Slot trống
```mermaid
sequenceDiagram
    actor KhachHang as Khách hàng
    participant UI as Giao diện Web
    participant Backend as Flask Controller
    participant DB as SQLite DB

    KhachHang ->> UI: Chọn Ngày khám & Bác sĩ
    UI ->> Backend: GET /api/slots?doctor_id=X&date=YYYY-MM-DD
    Backend ->> DB: Query ca trực (doctor_schedules)
    DB -->> Backend: Trả về ca trực
    Backend ->> DB: Query slot bận (appointments WHERE status <> 'Đã hủy')
    DB -->> Backend: Danh sách slot bận
    Backend -->> UI: JSON: { slots: ["08:00", "09:00", ...] }
    UI -->> KhachHang: Hiển thị các nút chọn giờ trống
```

---

## 5. Ma trận phân quyền (RBAC Matrix)

| Chức năng / Endpoint | Khách vãng lai | CUSTOMER | DOCTOR | CASHIER | ADMIN |
|---|:---:|:---:|:---:|:---:|:---:|
| Trang chủ, Dịch vụ, Bác sĩ | ✅ | ✅ | ✅ | ✅ | ✅ |
| Đặt lịch trực tuyến | ✅ | ✅ | ❌ | ❌ | ✅ |
| Quản lý thú cưng, tiêm phòng | ❌ | ✅ | ❌ | ❌ | ❌ |
| Lập bệnh án, kê đơn | ❌ | ❌ | ✅ | ❌ | ✅ |
| Duyệt lịch, Lập hóa đơn | ❌ | ❌ | ❌ | ✅ | ✅ |
| Quản lý nhân sự, dịch vụ, doanh thu | ❌ | ❌ | ❌ | ❌ | ✅ |
