;;; export_polyline_pts.lsp  v3
;;; Xuat toa do dinh LWPOLYLINE / POLYLINE / 3DPOLYLINE ra TXT: STT,X,Y
;;; Lenh XPLPTS     = toan bo ban ve, file mac dinh
;;; Lenh XPLPTS_SEL = chon tay, hoi file xuat

(defun _lw-pts (ent / ed pair result)
  ;; LWPOLYLINE: group code 10 = (10 x y) moi dinh
  (setq ed     (entget ent)
        result '())
  (foreach pair ed
    (if (= (car pair) 10)
      (setq result (append result (list (cdr pair))))))
  result)

(defun _write-pt (f stt pt)
  (write-line
    (strcat (itoa stt) ","
            (rtos (car  pt) 2 6) ","
            (rtos (cadr pt) 2 6))
    f))

(defun _proc-ent (ent f stt / typ elist vert-ent pt pts)
  ;; Tra ve stt moi sau khi ghi. Dung entget thuan tuy, khong dung VLA.
  (setq elist (entget ent))
  (if (not elist) (return stt))
  (setq typ (cdr (assoc 0 elist)))
  (cond
    ;; ── LWPOLYLINE: lay group code 10 truc tiep ──────────────────────────────
    ((= typ "LWPOLYLINE")
     (setq pts (_lw-pts ent))
     (foreach pt pts
       (_write-pt f stt pt)
       (setq stt (1+ stt))))

    ;; ── POLYLINE 2D / 3D: duyet VERTEX → SEQEND ──────────────────────────────
    ((= typ "POLYLINE")
     (setq vert-ent (entnext ent))
     (while (and vert-ent
                 (not (eq (cdr (assoc 0 (entget vert-ent))) "SEQEND")))
       (if (= (cdr (assoc 0 (entget vert-ent))) "VERTEX")
         (progn
           (setq pt (cdr (assoc 10 (entget vert-ent))))
           (if pt
             (progn
               (_write-pt f stt pt)
               (setq stt (1+ stt))))))
       (setq vert-ent (entnext vert-ent))))

    ;; ── 3DPOLYLINE: duyet VERTEX → SEQEND (tuong tu POLYLINE) ───────────────
    ((= typ "3DPOLYLINE")
     (setq vert-ent (entnext ent))
     (while (and vert-ent
                 (not (eq (cdr (assoc 0 (entget vert-ent))) "SEQEND")))
       (if (= (cdr (assoc 0 (entget vert-ent))) "VERTEX")
         (progn
           (setq pt (cdr (assoc 10 (entget vert-ent))))
           (if pt
             (progn
               (_write-pt f stt pt)
               (setq stt (1+ stt))))))
       (setq vert-ent (entnext vert-ent))))
  )
  stt)

;;; ════════════════════════════════════════════════════════════════════════════
;;; XPLPTS — toan bo ban ve, xuat vao file mac dinh
;;; ════════════════════════════════════════════════════════════════════════════
(defun c:XPLPTS ( / ss i ent file-path f stt total skipped result)

  (setq file-path
    "G:\\My Drive\\202605-TRUNG TAM HCM\\KET CAU KE\\pnbay-toa dobinhdoke.txt")

  (setq ss (ssget "_X" '((0 . "LWPOLYLINE,POLYLINE,3DPOLYLINE"))))
  (if (not ss)
    (progn (princ "\nKhong tim thay polyline trong ban ve.") (exit)))

  (setq total (sslength ss))
  (princ (strcat "\nTim thay " (itoa total) " polyline. Dang xuat..."))

  (setq f (open file-path "w"))
  (if (not f)
    (progn
      (princ (strcat "\nLoi: Khong mo duoc file " file-path))
      (exit)))

  (write-line "STT,X,Y" f)
  (setq stt     1
        skipped 0
        i       0)

  (while (< i total)
    (setq ent (ssname ss i))
    ;; Boc vl-catch-all-apply: skip entity loi, khong dung ca lenh
    (setq result
      (vl-catch-all-apply '_proc-ent (list ent f stt)))
    (if (vl-catch-all-error-p result)
      (setq skipped (1+ skipped))  ; bo qua entity loi
      (setq stt result))           ; cap nhat stt
    (setq i (1+ i)))

  (close f)
  (princ (strcat "\nHoan thanh! Xuat " (itoa (1- stt)) " diem"
                 (if (> skipped 0)
                   (strcat " (" (itoa skipped) " entity bi bo qua)")
                   "") "."))
  (princ (strcat "\nFile: " file-path))
  (princ))

;;; ════════════════════════════════════════════════════════════════════════════
;;; XPLPTS_SEL — chon tay polyline
;;; ════════════════════════════════════════════════════════════════════════════
(defun c:XPLPTS_SEL ( / ss i ent file-path f stt total skipped result)

  (princ "\nChon cac POLYLINE can xuat: ")
  (setq ss (ssget '((0 . "LWPOLYLINE,POLYLINE,3DPOLYLINE"))))
  (if (not ss)
    (progn (princ "\nKhong co doi tuong duoc chon.") (exit)))

  (setq file-path
    (getfiled "Chon file xuat toa do"
              "G:\\My Drive\\202605-TRUNG TAM HCM\\KET CAU KE\\"
              "txt" 1))
  (if (not file-path)
    (progn (princ "\nHuy lenh.") (exit)))

  (setq total (sslength ss)
        f     (open file-path "w"))
  (if (not f)
    (progn (princ "\nLoi: Khong mo duoc file.") (exit)))

  (write-line "STT,X,Y" f)
  (setq stt     1
        skipped 0
        i       0)

  (while (< i total)
    (setq ent (ssname ss i))
    (setq result
      (vl-catch-all-apply '_proc-ent (list ent f stt)))
    (if (vl-catch-all-error-p result)
      (setq skipped (1+ skipped))
      (setq stt result))
    (setq i (1+ i)))

  (close f)
  (princ (strcat "\nHoan thanh! Xuat " (itoa (1- stt)) " diem"
                 (if (> skipped 0)
                   (strcat " (" (itoa skipped) " entity bi bo qua)")
                   "") "."))
  (princ (strcat "\nFile: " file-path))
  (princ))

(princ "\nLoad OK v3. Lenh: XPLPTS (toan ban ve) | XPLPTS_SEL (chon tay)")
(princ)
