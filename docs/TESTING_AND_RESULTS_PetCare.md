# BÁO CÁO KẾT QUẢ KIỂM THỬ VÀ TÀI LIỆU KẾT QUẢ DỰ ÁN
## Hệ thống Quản lý Trung tâm Thú y — **PetCare**

> **Tài liệu:** Testing Report, Demonstration Script & Project Results  
> **Phiên bản:** 1.0 | **Ngày hoàn thành:** 16/11/2026 | **Mục đích:** Nộp đồ án & Trình bày hội đồng

---

## 1. Kết quả kiểm thử tự động (Automated Tests)
- **Tổng số test cases:** 29 ca kiểm thử tự động với Pytest.
- **Tỷ lệ vượt qua:** 100% (29/29 PASSED).
- **Phạm vi kiểm thử:** Xác thực, phân quyền RBAC 403, CSRF Token, kiểm tra slot trống, hủy lịch >4h, lập hóa đơn và lưu trữ persistence.

---

## 2. Kịch bản chạy Demo 7 bước (UAT Walkthrough)
1. **Bước 1:** Khách hàng đăng ký tài khoản, thêm hồ sơ thú cưng và mũi tiêm vắc-xin.
2. **Bước 2:** Khách hàng chọn bác sĩ, ngày và khung giờ trống để đặt lịch trực tuyến.
3. **Bước 3:** Thu ngân duyệt lịch hẹn từ trạng thái 'Chờ duyệt' sang 'Đã xác nhận'.
4. **Bước 4:** Bác sĩ mở ca khám, đo sinh hiệu (nhiệt độ, tim, cân nặng), chẩn đoán, kê đơn thuốc và hẹn ngày tái khám.
5. **Bước 5:** Thu ngân lập hóa đơn (phí khám + tiền thuốc + phụ thu), chọn Chuyển khoản và in phiếu thu PDF.
6. **Bước 6:** Khách hàng kiểm tra lịch sử bệnh án và hóa đơn trực tuyến trên tài khoản của mình.
7. **Bước 7:** Quản trị viên (Admin) xem Dashboard thống kê doanh thu, biểu đồ tài chính 7 ngày và quản lý nhân sự.
