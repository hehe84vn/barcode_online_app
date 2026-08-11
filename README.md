# Barcode / DataMatrix Online Generator

MVP Streamlit app để đọc Excel và xuất SVG / EPS / PDF / ZIP cho EAN-13, UPC-A và DataMatrix.

App có 2 chế độ generate độc lập:

- `Barcode + DataMatrix`: flow EAN/UPC hiện có.
- `DataMatrix only`: mã hóa nguyên nội dung cột `Data`, dùng `Name` làm nhãn đặt tên file.

## Cài đặt

```bash
python -m venv .venv
source .venv/bin/activate  # macOS/Linux
pip install -r requirements.txt
```

Đặt font Arial vào:

```text
fonts/Arial.ttf
```

> Font không được đóng gói trong project. Hãy copy font nội bộ vào thư mục `fonts/` trước khi chạy.

## Chạy app

```bash
streamlit run app.py
```

## Excel input

### Barcode + DataMatrix

Cần có 3 cột:

```text
Communication number
EAN/UPC
Product Version no.
```

### DataMatrix only

Cột bắt buộc và tùy chọn:

```text
Data    (bắt buộc, được mã hóa nguyên vẹn)
Name    (tùy chọn, nhãn tự do để đặt tên file)
```

- Header không phân biệt chữ hoa/chữ thường.
- Nên format cột `Data` là Text trong Excel để giữ số 0 đầu.
- Không trim hoặc loại bỏ ký tự khỏi payload. App chỉ cảnh báo nếu có khoảng trắng đầu/cuối.
- Cặp `Name + Data` giống hệt nhau chỉ generate một lần.

Tên file DataMatrix-only có dạng:

```text
{SAFE_NAME}__{DATA_OR_HASH}_DATAMATRIX.ext
```

Payload ngắn và an toàn được đưa trực tiếp vào tên file. Payload dài hoặc chứa ký tự đặc biệt dùng hash 8 ký tự; nội dung được mã hóa vẫn giữ nguyên.

## Output

App tạo ZIP gồm:

```text
BARCODE_YYYYMMDD_HHMMSS/
├── svg/
│   ├── EAN/
│   ├── UPC/
│   ├── DATAMATRIX_EAN/
│   └── DATAMATRIX_UPC/
└── dist/
    ├── EAN/EAN_EPS, EAN_PDF
    ├── UPC/UPC_EPS, UPC_PDF
    ├── DATAMATRIX_EAN/EAN_DATAMATRIX_EPS, EAN_DATAMATRIX_PDF
    └── DATAMATRIX_UPC/UPC_DATAMATRIX_EPS, UPC_DATAMATRIX_PDF
```

ZIP của chế độ DataMatrix-only gồm:

```text
DATAMATRIX_YYYYMMDD_HHMMSS/
├── svg/DATAMATRIX/
├── dist/DATAMATRIX/DATAMATRIX_EPS/
├── dist/DATAMATRIX/DATAMATRIX_PDF/
└── manifest.csv
```

## Chuẩn in ấn đang áp dụng

- EPS vector, không raster cho barcode bars và text outline.
- Fill black: `C0 M0 Y0 K100`.
- Overprint: `true setoverprint`.
- Barcode PDF page: 50mm x 50mm.
- EPS crop theo artwork thật.
- Barcode EAN/UPC scale mặc định: 80%.
- DataMatrix output hiện tại: page/artwork 16mm x 16mm, có quiet zone 1mm mỗi cạnh.

## Lưu ý

- Phần DataMatrix ưu tiên `pyStrich` (pure Python). `pylibdmtx` là backend dự phòng.
- Nếu deploy trên VPS Ubuntu, có thể cần:

```bash
sudo apt-get update
sudo apt-get install -y libdmtx0b
```

- Sau khi chạy MVP, cần so sánh file EPS/PDF mới với output Illustrator cũ bằng Illustrator/Acrobat và test scan thực tế.
