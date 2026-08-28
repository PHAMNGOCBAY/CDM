# Tổng hợp Giá trị Thiết kế Cơ lý CDM theo Loại Xi Măng (sử dụng NumPyro)

> Phân tích Bayesian sử dụng PyMC backend NumPyro (Phân vị 5% thiết kế).

| Loại Xi Măng        | Hàm Lượng (kg/m3)   |   Số mẫu (n) |   qu Mean (kPa) |   qu 5% Bayes (kPa) |   E50 Mean (MPa) |   E50 5% Bayes (MPa) |   Thời gian lấy mẫu (s) |
|:--------------------|:--------------------|-------------:|----------------:|--------------------:|-----------------:|---------------------:|------------------------:|
| Tổng thể            | Tất cả              |           72 |          1250.1 |              1202   |             82.3 |                 78.8 |                    8.14 |
| Hoàng Thạch (PCB40) | 220                 |           12 |          1184.8 |              1122.8 |             74.2 |                 68.5 |                    2.89 |
| Hoàng Thạch (PCB40) | 240                 |           12 |          1378.2 |              1283.1 |             91.9 |                 88.2 |                    3.42 |
| Hoàng Thạch (PCB40) | 260                 |           12 |          1530.6 |              1422.5 |            107.1 |                100.5 |                    2.78 |
| Xỉ lò cao Tam Điệp  | 220                 |           12 |           911.4 |               856.1 |             56.5 |                 55.2 |                    3.09 |
| Xỉ lò cao Tam Điệp  | 240                 |           12 |          1163.1 |              1078.4 |             74.6 |                 71.3 |                    4.44 |
| Xỉ lò cao Tam Điệp  | 260                 |           12 |          1332.8 |              1260.3 |             89.4 |                 86.8 |                   10.33 |

## Biểu đồ Hậu nghiệm chi tiết

### Tổng thể - Tất cả kg/m3
![Tổng_thể_Tất_cả_numpyro](../images/posterior_cdm_Tổng_thể_Tất_cả_numpyro.png)

### Hoàng Thạch (PCB40) - 220 kg/m3
![Hoàng_Thạch_PCB40_220_numpyro](../images/posterior_cdm_Hoàng_Thạch_PCB40_220_numpyro.png)

### Hoàng Thạch (PCB40) - 240 kg/m3
![Hoàng_Thạch_PCB40_240_numpyro](../images/posterior_cdm_Hoàng_Thạch_PCB40_240_numpyro.png)

### Hoàng Thạch (PCB40) - 260 kg/m3
![Hoàng_Thạch_PCB40_260_numpyro](../images/posterior_cdm_Hoàng_Thạch_PCB40_260_numpyro.png)

### Xỉ lò cao Tam Điệp - 220 kg/m3
![Xỉ_lò_cao_Tam_Điệp_220_numpyro](../images/posterior_cdm_Xỉ_lò_cao_Tam_Điệp_220_numpyro.png)

### Xỉ lò cao Tam Điệp - 240 kg/m3
![Xỉ_lò_cao_Tam_Điệp_240_numpyro](../images/posterior_cdm_Xỉ_lò_cao_Tam_Điệp_240_numpyro.png)

### Xỉ lò cao Tam Điệp - 260 kg/m3
![Xỉ_lò_cao_Tam_Điệp_260_numpyro](../images/posterior_cdm_Xỉ_lò_cao_Tam_Điệp_260_numpyro.png)

