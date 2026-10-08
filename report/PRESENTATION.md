# Kịch bản trình bày 3 phút — Topic A

## 0:00–0:30 — Câu hỏi và claim

“Nếu giá đỡ LiDAR bị lệch sau va chạm, projection sai bao nhiêu và có thể tự cảnh báo không?
Tôi chạy trên 20 frame KITTI và 80 frame nuScenes. Với yaw +3°, tỷ lệ điểm vật thể chiếu đúng box giảm 23,66 và 30,35 điểm phần trăm.
Nhưng tỷ lệ trong box không đủ để kết luận calibration đúng.”

## 0:30–1:15 — Phương pháp

Mở `results/figures/calibration_sweep.png`. Giải thích chuỗi `P2 × R0_rect × Tr_velo_to_cam`;
phải chia tọa độ đồng nhất, loại NaN/Inf, điểm sau camera và ngoài ảnh.
Chỉ thay calibration: yaw chín mức, dịch ngang bảy mức, thêm bốn mức yaw nhỏ.
Giữ nguyên điểm thuộc box 3D và FOV baseline; điểm mất FOV được tính là không khớp.
Score là số điểm chiếu vào box 2D tương ứng chia số điểm cố định ban đầu; cảnh báo khi giảm ít nhất 10 điểm phần trăm.

## 1:15–2:15 — Kết quả và failure

Mở `fail_01_geometry_yaw.png`: KITTI 000061, yaw −3°, 108/108 điểm thành 0/108, dịch 62,10 px.
Đây là lỗi Geometry do calibration drift giả lập; object bị cắt bởi mép ảnh nên rất nhạy.
Mở `fail_02_metric_missed_drift.png`: nuScenes scene-1094_008, yaw −2°, xe dịch 60,62 px nhưng 31/31 điểm vẫn trong box.
Score frame chỉ giảm 6,63 pp, dưới ngưỡng 10: lỗi Metric do box rộng và gộp điểm che lỗi từng object.
Ở +1°, chỉ 55% frame KITTI và 43,75% frame nuScenes được cảnh báo. Ngưỡng này chưa được xác nhận cho hệ thống thật.

## 2:15–3:00 — Ứng dụng và kiểm chứng

Trong ADAS, dùng score làm một tín hiệu QA bổ trợ, kết hợp cạnh ảnh, nhóm khoảng cách và kiểm tra đồng bộ thời gian.
Log support count, tỷ lệ invalid/FOV, score từng object, timestamp và calibration version.
Score này cần GT và calibration baseline; muốn chạy online phải xây tham chiếu độc lập và đánh giá báo động giả trên log sạch riêng.
Tất cả số liệu chạy thật, hai lần ra CSV giống từng byte. Tôi dùng Codex và khai báo trong báo cáo.

## Câu hỏi thường gặp

- **Vì sao điểm LiDAR `(10,0,0)` có depth dương?** KITTI x hướng trước, camera z hướng trước; calibration chuyển x LiDAR sang z camera. Với synthetic, depth khoảng 9,73 m và pixel gần (614,175).
- **Yaw có cùng trục trên hai dataset không?** Cùng xoay quanh z-up; KITTI x-forward/y-left, nuScenes x-right/y-forward. Dịch ngang dùng y KITTI và x nuScenes; dấu dịch ngang không cùng hướng trái/phải.
- **Vì sao nuScenes dịch pixel lớn hơn?** Tiêu cự theo pixel lớn hơn và ảnh 1600×900; số beam, bố cục cảnh và số điểm ảnh hưởng score. Không thể quy toàn bộ khác biệt cho số beam hay ngày/đêm.
- **Score 100% có chứng minh calibration đúng không?** Không. NuScenes box 2D được suy ra từ box 3D bằng baseline, nên baseline gần 100% có tính phụ thuộc; failure đã chứng minh box rộng vẫn chứa điểm lệch.
- **p50/p95 trong bảng có phải latency không?** Không: đó là độ dịch pixel. Bài này không benchmark thời gian chạy.
- **Có thể giải thích mọi dòng code chưa?** Cần tự đọc `src/projection_qa.py`, chạy kiểm thử và tập giải thích trước khi vấn đáp; kiểm thử tự động không thay thế hiểu biết của học viên.
