# Tổng hợp Giá trị Thiết kế Cơ lý Đất (Phân vị 5% Bayes)

> Lọc từ CSDL `data/TTHC.sqlite` và phân tích tự động bằng mô hình NUTS (PyMC).
> **Ghi chú:** Máy đã được cài C++ compiler (`g++`) nên độ chính xác được đẩy lên tối đa (`draws=2000, tune=1000`).

| Lớp   |   Số mẫu (n) |   c_mean (kPa) |   c_design (kPa) |   Giảm c (%) |   phi_mean (độ) |   phi_design (độ) |   Giảm phi (%) |
|:------|-------------:|---------------:|-----------------:|-------------:|----------------:|------------------:|---------------:|
| 1     |          103 |           7.16 |             6.51 |         -9   |            4.64 |              4.3  |           -7.3 |
| 1b    |            7 |          12.85 |             9.39 |        -26.9 |           13.78 |             10.52 |          -23.7 |
| 2     |          130 |           5.94 |             5.61 |         -5.5 |            3.95 |              3.71 |           -6.1 |
| 2b    |            6 |          13.52 |            11.48 |        -15   |           13.15 |             10.4  |          -20.9 |
| 3     |           31 |          14.25 |            12.31 |        -13.7 |           10.44 |              9.11 |          -12.7 |
| 3b    |            7 |          10.76 |             9.56 |        -11.1 |           21.05 |             19.67 |           -6.6 |
| 4     |           38 |          23.72 |            21.29 |        -10.2 |           15.16 |             13.63 |          -10.1 |
| 5     |           40 |          29.51 |            27.48 |         -6.9 |           17.74 |             17.01 |           -4.1 |
| 6     |           96 |          33.01 |            31.37 |         -5   |           17.2  |             16.68 |           -3   |
| 7     |           21 |          26.51 |            22.14 |        -16.5 |           19.76 |             18.35 |           -7.1 |
| 8     |            9 |          26.06 |            19.61 |        -24.8 |           20.65 |             18.14 |          -12.1 |
| TK6a  |            6 |          29.25 |            22.44 |        -23.3 |           17.31 |             15.1  |          -12.8 |

## Biểu đồ Hậu nghiệm

### Lớp 1
![Lớp 1](../images/soil_posterior_layer_1.png)

### Lớp 1b
![Lớp 1b](../images/soil_posterior_layer_1b.png)

### Lớp 2
![Lớp 2](../images/soil_posterior_layer_2.png)

### Lớp 2b
![Lớp 2b](../images/soil_posterior_layer_2b.png)

### Lớp 3
![Lớp 3](../images/soil_posterior_layer_3.png)

### Lớp 3b
![Lớp 3b](../images/soil_posterior_layer_3b.png)

### Lớp 4
![Lớp 4](../images/soil_posterior_layer_4.png)

### Lớp 5
![Lớp 5](../images/soil_posterior_layer_5.png)

### Lớp 6
![Lớp 6](../images/soil_posterior_layer_6.png)

### Lớp 7
![Lớp 7](../images/soil_posterior_layer_7.png)

### Lớp 8
![Lớp 8](../images/soil_posterior_layer_8.png)

### Lớp TK6a
![Lớp TK6a](../images/soil_posterior_layer_TK6a.png)

