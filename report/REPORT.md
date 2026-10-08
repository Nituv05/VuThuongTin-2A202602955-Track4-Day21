# Báo cáo Day 6: Độ nhạy projection LiDAR–camera với calibration drift

- **Họ tên:** Vũ Thường Tín
- **MSSV:** 2A202602955
- **Lớp:** K4 Track 4
- **Link repo:** https://github.com/Nituv05/K4-Track4-Day06-VuThuongTin-2A202602955-3D-From-Point-Clouds
- **Topic:** A — LiDAR-camera projection QA, mức Advanced
- **Dataset:** `data/synthetic` để kiểm thử; `data/kitti_mini` và `data/nuscenes_mini_subset` để benchmark.
- **Các frame đã dùng:** KITTI: 000001, 000004, 000007, 000008, 000009, 000010, 000011, 000012, 000015, 000016, 000019, 000021, 000023, 000025, 000031, 000032, 000043, 000048, 000049, 000061; nuScenes: scene-0103_000–039 và scene-1094_000–039. Xem [frames.csv](../results/frames.csv).

## 1. Claim

**Trên 20 frame KITTI và 80 frame nuScenes, yaw drift +3° làm tỷ lệ điểm của vật thể chiếu vào đúng box 2D giảm lần lượt 23,66 và 30,35 điểm phần trăm so với baseline.** Ở +1°, ngưỡng giảm 10 điểm phần trăm chỉ cảnh báo 55% frame KITTI và 43,75% frame nuScenes: score trong box có thể bỏ sót drift đáng kể. Đây là kết quả trên subset đã khảo sát, không phải bảo đảm cho mọi sensor hoặc điều kiện vận hành.

## 2. Evidence

Chạy **2.000 cấu hình trên 100 frame**, gồm yaw `0, ±0.5, ±1, ±2, ±3°`, dịch ngang `0, ±2, ±5, ±10 cm` và yaw nhỏ `±0.1, ±0.25°`; mỗi lần chỉ thay một yếu tố. Giữ nguyên frame, label, tập điểm baseline và bù ego motion nuScenes; không lấy mẫu ngẫu nhiên, seed ghi nhận là 42.

**Score** là tỷ lệ điểm thuộc box 3D và FOV baseline còn chiếu vào box 2D tương ứng; mẫu số cố định, điểm mất FOV tính là mismatch. Cảnh báo từng frame khi score giảm **≥10 pp**. Ngưỡng được chọn trước sweep để minh họa: với mẫu số 100 cặp điểm–object, giảm 10 cặp đúng box tương ứng giảm 10 pp; chưa tối ưu hoặc xác nhận trên log sạch độc lập.

| Dataset | Yaw | Score đúng box (%) | Giảm (pp) | Dịch pixel* | Frame cảnh báo (%) |
|---|---|---:|---:|---:|---:|
| KITTI | 0° | 99,565 | 0,000 | 0,00 | 0 |
| KITTI | +1° | 92,839 | 6,725 | 14,58 | 55 |
| KITTI | +3° | 75,905 | 23,660 | 43,50 | 100 |
| nuScenes | 0° | 99,937 | 0,000 | 0,00 | 0 |
| nuScenes | +1° | 92,161 | 7,776 | 25,18 | 43,75 |
| nuScenes | +3° | 69,586 | 30,351 | 75,24 | 100 |

*Dịch pixel là trung vị của p50 từng frame trên các điểm còn trong cả hai FOV. Score gộp theo số cặp điểm–object, còn tỷ lệ cảnh báo đếm frame. Kết quả đầy đủ: [calibration_summary.csv](../results/calibration_summary.csv); phương pháp và các bảng chi tiết: [APPENDIX.md](APPENDIX.md).

![Độ nhạy score và độ dịch pixel theo calibration drift](../results/figures/calibration_sweep.png)

![Tỷ lệ frame cảnh báo và score bỏ sót yaw nhỏ](../results/figures/drift_detection.png)

Ở yaw +3°, nhóm xa >30 m giảm score 74,28 pp KITTI / 63,78 pp nuScenes, lớn hơn nhóm gần <10 m (13,90 / 19,63 pp). Với +0,25° nuScenes, độ dịch tổng hợp 6,31 px nhưng không frame nào cảnh báo. Ba ảnh demo gần/trung bình/xa và ảnh hưởng dịch ngang nằm trong phụ lục.

nuScenes có ít điểm hơn (trung bình 34.718,80 so với 119.318,45 KITTI), ảnh/tiêu cự theo pixel khác và timestamp lệch; không quy toàn bộ khác biệt cho số beam hay ngày/đêm. **Box 2D nuScenes do starter suy ra từ box 3D bằng calibration baseline**, nên score gần 100% không phải kiểm chứng calibration độc lập. Hai lần chạy cho 6 CSV benchmark và config giống từng byte. Nguồn ảnh: KITTI Vision Benchmark Suite và nuScenes (Motional).

## 3. Failure case

![Lỗi hình học do yaw drift](../results/figures/fail_01_geometry_yaw.png)

**Geometry:** KITTI `000061`, Car #1 ở 14,81 m, yaw −3°: từ **108/108** điểm trong box xuống **0/108**, dịch p50 **62,10 px**. Calibration drift làm điểm chiếu sang vị trí không còn khớp xe; đây là drift giả lập, không phải lỗi dataset gốc. Object bị cắt bởi mép ảnh (`truncated=0,79`), nên rất nhạy và không đại diện mọi xe. Phát hiện bằng score từng object cùng overlay, kiểm tra extrinsic và giá đỡ sensor.

![Score bỏ sót drift](../results/figures/fail_02_metric_missed_drift.png)

**Metric:** nuScenes `scene-1094_008`, Car #0 ở 20,50 m, yaw −2°: dịch p50 **60,62 px** nhưng vẫn **31/31** điểm trong box rộng. Score object không giảm; score frame chỉ giảm **6,63 pp**, dưới ngưỡng 10, nên không cảnh báo dù p50 cả frame dịch 50,46 px. Box rộng và việc gộp theo số điểm che lỗi. Khắc phục bằng kiểm tra từng object/nhóm khoảng cách và thêm score khớp cạnh ảnh hoặc mốc calibration độc lập; không chứng nhận calibration đúng chỉ vì score cao. Với yaw nhỏ, +0,25° trên nuScenes dịch p50 tổng hợp 6,31 px nhưng không frame nào cảnh báo. Xem [evidence.csv](../results/evidence.csv).

## 4. Khuyến nghị nếu triển khai thật

- **Use-case ADAS:** QA calibration LiDAR–camera trước khi fusion hoặc hỗ trợ gán nhãn; đưa frame thiếu support vào hàng chờ review, không tự động coi là dữ liệu sạch.
- Ghi log số điểm hữu hạn, tỷ lệ FOV, điểm mất FOV, support từng object, score theo khoảng cách/class, timestamp gap và phiên bản calibration. Tỷ lệ FOV gần như không đổi ở sweep yaw nên riêng chỉ số này không đủ phát hiện drift.
- Ngưỡng **10 pp là lựa chọn thử nghiệm**, chưa hiệu chỉnh trên tập log sạch độc lập; mức 0° so với chính baseline không đo được báo động giả trong vận hành. Score hiện cần GT và calibration baseline, nên là công cụ offline; phiên bản online cần tham chiếu độc lập, kiểm tra nhạy/báo động giả và bù chuyển động vật thể.
- Vector hóa projection phù hợp CPU, nhưng vẽ overlay và xử lý toàn bộ frame có chi phí. Có thể QA định kỳ hoặc lấy mẫu điểm để giảm tải, rồi đánh giá lại độ nhạy với vật nhỏ/xa. Bài này không đo latency và không khẳng định đáp ứng thời gian thực.

## 5. Cách chạy lại

Chạy từ gốc repo, dùng Python **3.12**. Các phiên bản đã kiểm chứng được ghim trong [requirements-repro.txt](../src/requirements-repro.txt); dữ liệu đã có sẵn, không cần tải thêm.

```bash
python3.12 -m venv .venv
source .venv/bin/activate
python -m pip install -r src/requirements-repro.txt
export MPLCONFIGDIR=/tmp/day6-mpl
python tools/verify_data.py --data-root data/kitti_mini
python tools/verify_data.py --data-root data/nuscenes_mini_subset
python -m unittest src.test_projection_qa
python -m starter.projection --data-root data/synthetic --frame 000000
python -m starter.projection --data-root data/kitti_mini --frame 000011
python -m starter.projection --data-root data/nuscenes_mini_subset --frame scene-0103_010
python -m src.projection_qa --seed 42 --threshold-pp 10
python -m src.projection_qa --seed 42 --threshold-pp 10 --skip-figures --out-dir /tmp/day6-qa-repeat
python -m src.check_results --compare-dir /tmp/day6-qa-repeat
python tools/check_submission.py
```

CLI tùy chọn: `python -m src.projection_qa --help`; chạy một dataset/frame: `python -m src.projection_qa --data-roots data/kitti_mini --frames 000011 --skip-figures --out-dir /tmp/day6-single`. Bộ tạo ba ảnh demo mặc định cần đủ nhóm gần/trung bình/xa; dùng `--skip-figures` cho subset nhỏ. [experiment_config.json](../results/experiment_config.json) lưu frame, metric, threshold, hệ điều hành và phiên bản thư viện; số liệu có thể sai khác ở mức floating-point giữa nền tảng, PNG có thể khác do font. Chỉ hai thân hàm TODO được sửa trong starter; code bổ sung ở src; dữ liệu gốc được giữ nguyên. Kịch bản vấn đáp: [PRESENTATION.md](PRESENTATION.md).

## 6. Khai báo sử dụng AI

| Công cụ | Dùng cho việc gì | Kiểm chứng do agent thực hiện |
|---|---|---|
| OpenAI Codex | Đọc yêu cầu, lập kế hoạch, cài đặt projection và CLI benchmark, kiểm thử, phân tích failure, soạn báo cáo và hướng dẫn trình bày | Chạy 9 kiểm thử hình học/metric; điểm synthetic `(10,0,0)` cho z≈9,73 m, pixel≈(614,175); xem ảnh baseline/failure; chạy hai lần so CSV/config giống từng byte; kiểm tra checksum dữ liệu và submission checker |

**Kiểm chứng cá nhân của học viên: chưa được xác nhận trong phiên làm việc.** Các bước và kết quả cần tự đối chiếu nằm trong [APPENDIX.md](APPENDIX.md). Sau khi thực hiện, bổ sung kết quả thực tế vào mục này. Mọi ảnh minh chứng là projection/plot từ code và dữ liệu đề bài; không dùng ảnh AI tạo sinh hoặc số liệu bịa.
