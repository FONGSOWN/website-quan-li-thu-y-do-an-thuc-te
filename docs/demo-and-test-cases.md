# Kịch bản demo và kiểm thử

## Kịch bản demo

1. Đăng ký khách hàng, thêm thú cưng và một mũi tiêm.
2. Quản trị viên thêm bác sĩ, tạo lịch trực trong database hoặc dữ liệu demo.
3. Khách chọn bác sĩ, ngày, khung giờ rồi đặt lịch.
4. Thu ngân duyệt lịch; khách nhận thông báo.
5. Bác sĩ mở ca khám, ghi bệnh án và hoàn tất.
6. Thu ngân lập hóa đơn, chọn phương thức thanh toán và bấm **In / Lưu PDF**.
7. Khách mở lịch sử để xem hóa đơn; admin xem số liệu doanh thu.

## Test case trọng tâm

| Mã | Tình huống | Kết quả mong đợi |
|---|---|---|
| TC01 | Đăng ký trùng email | Bị từ chối |
| TC02 | Pet thuộc khách khác | Trả 404/403 |
| TC03 | Hai lịch cùng bác sĩ/slot | Ràng buộc SQLite chặn lịch sau |
| TC04 | Hủy dưới 4 giờ | Bị chặn |
| TC05 | File `.exe` | Bị từ chối |
| TC06 | Hóa đơn trùng lịch hẹn | Bị chặn bởi unique constraint |
| TC07 | Khách xem hóa đơn người khác | Trả 403 |
