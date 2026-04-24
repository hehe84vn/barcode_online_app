# Checklist kiểm tra output in ấn

Sau khi generate batch mẫu, mở EPS/PDF trong Illustrator/Acrobat và kiểm tra:

1. **EPS là vector**
   - Zoom lớn không vỡ.
   - Barcode/DataMatrix là object/path/rect, không phải image raster.

2. **Màu đen**
   - Fill phải là `C0 M0 Y0 K100`.
   - Không dùng RGB black.
   - Không rich black.

3. **Overprint**
   - Fill Overprint phải bật.
   - Kiểm tra bằng Attributes panel trong Illustrator hoặc Output Preview trong Acrobat.

4. **Kích thước**
   - DataMatrix artwork khoảng `16mm x 16mm`.
   - PDF page `50mm x 50mm`.
   - EPS crop theo artwork thật, không giữ artboard 50mm.

5. **EAN/UPC**
   - So sánh kích thước với file cũ.
   - Kiểm tra phần số dưới barcode đã outline/vector.
   - Scan thử barcode.

6. **Naming/folder**
   - Tên file và folder cần khớp workflow cũ.
