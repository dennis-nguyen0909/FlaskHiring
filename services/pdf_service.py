import PyPDF2

def extract_text_from_pdf(pdf_path):
    text = ""
    try:
        with open(pdf_path, "rb") as file:
            reader = PyPDF2.PdfReader(file)
            for page in reader.pages:
                text += page.extract_text() or ""
        return text
    except FileNotFoundError:
        raise FileNotFoundError(f"Không tìm thấy file PDF tại '{pdf_path}'")
    except Exception as e:
        raise Exception(f"Lỗi khi đọc PDF: {e}")
