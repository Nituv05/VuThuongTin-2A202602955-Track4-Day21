# Báo cáo Day 6: Độ nhạy projection LiDAR–camera với calibration drift

> Thay **mọi** ô có chữ ĐIỀN nằm trong ngoặc vuông bằng nội dung của bạn, xoá luôn cả dấu ngoặc vuông. Lệnh `python tools/check_submission.py` sẽ báo FAIL nếu còn sót bất kỳ chỗ nào.

- **Họ tên:** Vũ Thường Tín
- **MSSV:** 2A202602955
- **Lớp:** K4 Track 4
- **Link repo:** https://github.com/Nituv05/K4-Track4-Day06-VuThuongTin-2A202602955-3D-From-Point-Clouds
- **Topic:** A — LiDAR-camera projection QA (Advanced)
- **Dataset:** data/synthetic (kiểm thử), data/kitti_mini, data/nuscenes_mini_subset (benchmark)
- **Các frame đã dùng:** Toàn bộ 20 frame KITTI và 80 frame nuScenes; danh sách chi tiết sẽ xuất trong results/frames.csv.

> Hãy viết ngắn: mỗi mục từ 3 đến 8 dòng, ưu tiên số liệu và hình ảnh.

## 1. Claim

Một câu khẳng định kỹ thuật có thể kiểm chứng. Ví dụ: *"Lệch yaw 1° làm 12% điểm LiDAR rơi ra khỏi vật thể ở 30 m, phát hiện được bằng edge-alignment score với ngưỡng X."*

Giả thuyết CP1: yaw drift 0.5–3° làm tăng độ dịch pixel và giảm tỷ lệ điểm của vật thể chiếu vào đúng box 2D; ngưỡng giảm 10 điểm phần trăm có thể cảnh báo drift nhưng có thể bỏ sót drift nhỏ. Claim cuối cùng sẽ dựa trên số liệu chạy thật.

## 2. Evidence

Bảng hoặc plot số liệu, kèm ảnh/video demo. Ghi rõ đường dẫn file trong `results/`.

| Cấu hình / mức perturb | Metric 1 | Metric 2 | Ghi chú |
|---|---|---|---|
| [ĐIỀN] | | | |

![demo](../results/figures/[ĐIỀN].png)

## 3. Failure case

Nêu khi nào hệ thống hoặc phương pháp fail, vì sao fail, và liên hệ tới lớp nào trong 6 lớp debug: I/O, Geometry, Time, Preprocess, Model, Metric.

![failure](../results/figures/fail_[ĐIỀN].png)

[ĐIỀN]

## 4. Khuyến nghị nếu triển khai thật

Use-case cụ thể (ADAS / robot / drone), trade-off và bước tiếp theo.

[ĐIỀN]

## 5. Cách chạy lại

Các lệnh tái tạo lại toàn bộ kết quả từ repo sạch.

```bash
[ĐIỀN]
```

## 6. Khai báo sử dụng AI

Ghi rõ đã dùng công cụ AI nào, dùng vào việc gì, và bạn đã tự kiểm chứng kết quả đó bằng cách nào. Nếu không dùng AI, ghi "Không sử dụng". Xem quy định ở `RULES.md` mục 2.

| Công cụ | Dùng cho việc gì | Bạn đã kiểm chứng thế nào |
|---|---|---|
| [ĐIỀN] | | |
