# Barcode / DataMatrix Online Generator

MVP Streamlit app để đọc Excel và xuất SVG / EPS / PDF / ZIP cho EAN-13, UPC-A và DataMatrix.

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

Cần có 3 cột:

```text
Communication number
EAN/UPC
Product Version no.
```

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

## Chuẩn in ấn đang áp dụng

- EPS vector, không raster cho barcode bars và text outline.
- Fill black: `C0 M0 Y0 K100`.
- Overprint: `true setoverprint`.
- PDF page: 50mm x 50mm.
- EPS crop theo artwork thật.
- Barcode EAN/UPC scale mặc định: 80%.
- DataMatrix artwork mặc định: 16mm x 16mm, đặt trong page 50mm.

## Lưu ý

- Phần DataMatrix cần `pylibdmtx` và native `libdmtx` trên server.
- Nếu deploy trên VPS Ubuntu, có thể cần:

```bash
sudo apt-get update
sudo apt-get install -y libdmtx0b
```

- Sau khi chạy MVP, cần so sánh file EPS/PDF mới với output Illustrator cũ bằng Illustrator/Acrobat và test scan thực tế.
