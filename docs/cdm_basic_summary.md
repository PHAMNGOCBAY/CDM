# Phân tích NumPyro độc lập cho mẫu 7 ngày và 28 ngày (qu & E50)

> **Bảng so sánh Truyền thống vs Bayesian:** Bảng dưới đây đối chiếu giá trị trung bình cộng (Mean Truyền thống) và công thức tính 5%, 10% so với phân phối hậu nghiệm Bayesian.

| Chỉ tiêu | Tuổi (ngày) | Hàm lượng | Số mẫu (n) | Mean (TT) | 5% (TT) | 10% (TT) | Mean (Bayes) | 5% (Bayes) | 10% (Bayes) |
|----------|-------------|-----------|------------|-----------|---------|----------|--------------|------------|-------------|
| qu | 7 | 220.0 | 4 | 458.9 | 242.4 | 290.2 | 469.8 | 297.2 | 341.5 |
| qu | 7 | 240.0 | 4 | 482.5 | 270.5 | 317.3 | 498.3 | 328.4 | 377.3 |
| qu | 7 | 260.0 | 4 | 537.1 | 279.3 | 336.2 | 550.7 | 358.6 | 408.1 |
| qu | 28 | 220.0 | 24 | 1048.1 | 752.8 | 817.9 | 1049.0 | 983.5 | 999.6 |
| qu | 28 | 240.0 | 24 | 1270.6 | 929.1 | 1004.5 | 1270.2 | 1197.7 | 1215.1 |
| qu | 28 | 260.0 | 24 | 1431.7 | 1095.1 | 1169.4 | 1431.3 | 1356.0 | 1375.1 |
| e50 | 7 | 220.0 | 4 | 35.2 | 21.0 | 24.1 | 36.6 | 24.2 | 27.3 |
| e50 | 7 | 240.0 | 4 | 38.3 | 21.7 | 25.4 | 39.9 | 25.1 | 29.6 |
| e50 | 7 | 260.0 | 4 | 41.6 | 24.5 | 28.3 | 43.3 | 28.8 | 32.6 |
| e50 | 28 | 220.0 | 24 | 65.4 | 45.7 | 50.0 | 65.5 | 61.3 | 62.2 |
| e50 | 28 | 240.0 | 24 | 83.2 | 65.3 | 69.3 | 83.2 | 79.5 | 80.4 |
| e50 | 28 | 260.0 | 24 | 98.2 | 76.7 | 81.4 | 98.3 | 93.4 | 94.5 |

## Biểu đồ So sánh Hàm lượng Xi măng
Các biểu đồ dưới đây đặt chồng phân phối Hậu nghiệm của 3 cấp hàm lượng xi măng (220, 240, 260) lên cùng một trục đồ thị để dễ dàng nhận thấy sự dịch chuyển cường độ sang phải khi tăng hàm lượng xi măng.

### So sánh Cường độ nén qu
![So sánh qu 28 ngày](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_comparison_qu_28d.png)

![So sánh qu 7 ngày](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_comparison_qu_7d.png)

### So sánh Mô-đun biến dạng E50
![So sánh E50 28 ngày](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_comparison_e50_28d.png)

![So sánh E50 7 ngày](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_comparison_e50_7d.png)


## Biểu đồ Hậu nghiệm Chi tiết (Từng tổ mẫu)
### qu - Tuổi 7 ngày - Hàm lượng 220 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_qu_7d_220.png)

### qu - Tuổi 7 ngày - Hàm lượng 240 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_qu_7d_240.png)

### qu - Tuổi 7 ngày - Hàm lượng 260 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_qu_7d_260.png)

### qu - Tuổi 28 ngày - Hàm lượng 220 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_qu_28d_220.png)

### qu - Tuổi 28 ngày - Hàm lượng 240 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_qu_28d_240.png)

### qu - Tuổi 28 ngày - Hàm lượng 260 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_qu_28d_260.png)

### e50 - Tuổi 7 ngày - Hàm lượng 220 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_e50_7d_220.png)

### e50 - Tuổi 7 ngày - Hàm lượng 240 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_e50_7d_240.png)

### e50 - Tuổi 7 ngày - Hàm lượng 260 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_e50_7d_260.png)

### e50 - Tuổi 28 ngày - Hàm lượng 220 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_e50_28d_220.png)

### e50 - Tuổi 28 ngày - Hàm lượng 240 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_e50_28d_240.png)

### e50 - Tuổi 28 ngày - Hàm lượng 260 kg/m3
![Posterior](G:/My Drive/AI-SUC TAI COC THEO DAT NEN/images/cdm_posterior_e50_28d_260.png)

