# THIẾT KẾ CẦU ĐƯỜNG BỘ - PHẦN 5: KẾT CẤU BÊ TÔNG (TCVN 11823-5:2017)

Tài liệu này lưu trữ các bước kiểm toán kết cấu chịu uốn và chịu cắt dựa trên hình ảnh cung cấp.

## IV.3.1. Số liệu đầu vào
- **Cường độ bê tông**: $f'_c = 30$ MPa (C30 – TCVN 11823-2017)
- **Cường độ thép**: $f_y = 300$ MPa (CB300-V – TCVN 1651-2)
- **Chiều dày bản / bề rộng**: $h = 200$ mm ; $b = 1000$ mm/m (Chiều dài tính toán L = 1,0 m)
- **Lớp bảo vệ bê tông**: $c = 40$ mm (Môi trường bình thường)
- **Chiều cao có ích**: $d = h - c - \phi/2 = 200 - 40 - 7 = 153$ mm (Giả sử thanh $\phi14$)

## IV.3.2. Hệ số vật liệu
- **Hệ số quy đổi khối ứng suất**: $\beta_1 = 0,85 - 0,05 \times (f'_c - 28) / 7 = 0,85 - 0,05 \times (30 - 28) / 7 = 0,836$
- **Hệ số sức kháng uốn (§5.5.4.2)**: $\phi_f = 0,90$ (cấu kiện chịu uốn – vùng kéo kiểm soát)
- **Hệ số sức kháng cắt (§5.5.4.2)**: $\phi_v = 0,90$ (cấu kiện chịu cắt)

## IV.3.4. Tính diện tích cốt thép yêu cầu
- **Mô men tính toán**: $M_u = 9,15$ kN.m
- **Hệ số sức kháng mômen danh định**: 
  $R_n = M_u / (\phi_f \cdot b \cdot d^2) = 9,15 \times 10^6 / (0,90 \times 1000 \times 153^2) = 0,434$ MPa
- **Hàm lượng cốt thép**: 
  $\rho = (0,85 \cdot f'_c / f_y) \times \left[ 1 - \sqrt{1 - 2 \cdot R_n / (0,85 \cdot f'_c)} \right]$
  $\rho = (0,85 \times 30 / 300) \times \left[ 1 - \sqrt{1 - 2 \times 0,434 / 25,5} \right] = 0,001459$
- **Diện tích cốt thép tính toán**:
  $A_{s,tt} = \rho \cdot b \cdot d = 0,001459 \times 1000 \times 153 = 223$ mm²/m

## IV.3.5. Kiểm tra cốt thép tối thiểu
- **Cường độ kéo khi uốn của bê tông**: $f_r = 0,63 \times \sqrt{f'_c} = 0,63 \times \sqrt{30} = 3,45$ MPa
- **Mômen nứt của mặt cắt nguyên**: $M_{cr} = f_r \times (b \cdot h^2 / 6) = 3,45 \times (1000 \times 200^2 / 6) = 23,0$ kN.m
- **Diện tích cốt thép không được nhỏ hơn giá trị ứng với nhỏ hơn của**:
  - $1,2 \times M_{cr} = 1,2 \times 23,0 = 27,6$ kN.m
  - $1,33 \times M_u = 1,33 \times 9,15 = 12,17$ kN.m $\leftarrow$ kiểm soát
- **Diện tích cốt thép tối thiểu ứng với $M_{min} = 12,17$ kN.m**:
  $R_{n,min} = 12,17 \times 10^6 / (0,90 \times 1000 \times 153^2) = 0,578$ MPa $\rightarrow \rho_{min} = 0,001949$
  $A_{s,min} = 0,001949 \times 1000 \times 153 = 298$ mm²/m

## IV.3.6. Kiểm toán chịu cắt
- **Lực cắt tính toán**: $Q_u = 15,80$ kN
- **a) Chiều cao chịu cắt có hiệu (§5.7.2.8)**:
  $d_v = \max(0,9 \cdot d ; 0,72 \cdot h) = \max(0,9 \times 153 ; 0,72 \times 200) = \max(137,7 ; 144,0) = 144$ mm
- **b) Sức kháng cắt của bê tông – phương pháp đơn giản hóa (§5.7.3.4.1)**:
  $V_c = 0,083 \times \beta \times \lambda \times \sqrt{f'_c} \times b_v \times d_v$
  $V_c = 0,083 \times 2,0 \times 1,0 \times \sqrt{30} \times 1000 \times 144 = 130,9$ kN
  Trong đó: $\beta = 2,0$ (bản sàn, phương pháp đơn giản); $\lambda = 1,0$ (BTCT thường)
- **c) Sức kháng cắt tính toán**:
  $\phi_v \times V_c = 0,90 \times 130,9 = 117,8$ kN
- **d) Kiểm tra điều kiện chịu cắt**:
  $Q_u = 15,80$ kN $< \phi_v \times V_c = 117,8$ kN $\rightarrow$ Bê tông đủ khả năng chịu cắt
- **e) Kiểm tra yêu cầu cốt thép ngang tối thiểu (§5.7.2.3)**:
  $Q_u = 15,80$ kN $< 0,5 \times \phi_v \times V_c = 58,9$ kN $\rightarrow$ Không cần cốt thép đai

## IV.3.7. Kết luận
- **Diện tích cốt thép thiết kế**: $A_s = \max(223 ; 298) = 298$ mm²/m (kiểm soát bởi $1,33 \cdot M_u$)
- **Cốt thép chọn**: $\phi12$ a350 $\rightarrow A_{s,chọn} = 323$ mm²/m $> 298$ mm²/m
- **Kiểm tra**: $\phi M_n = 13,18$ kN.m $> 12,17$ kN.m | Không cần cốt thép đai
