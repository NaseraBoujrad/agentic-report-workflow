import os
#from pypdf import PdfReader
import pdfplumber
import pytesseract

DATA_PATH = os.getcwd() + "/data/pdf"

def load_all_pdfs():
    documents = []

    for filename in os.listdir(DATA_PATH):
        if not filename.endswith(".pdf"):
            continue
        path = os.path.join(DATA_PATH, filename)
        print("Attempting to load:", path)

        full_text = ""
        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):
                    text = page.extract_text()
                    if text and text.strip():
                        full_text += text + "\n"
                    else:
                        # Fallback to OCR
                        image = page.to_image(resolution=300).original
                        ocr_text = pytesseract.image_to_string(image)
                        if ocr_text.strip():
                            full_text += ocr_text + "\n"
                        else:
                            print(f"Page {i} empty in {filename}")
        except Exception as e:
            print(f"Failed to open {filename}: {e}")
            continue

        if full_text.strip():
            documents.append({"filename": filename, "text": full_text})
        else:
            print(f"No text extracted from {filename}")

    print("Total PDFs loaded:", len(documents))
    return documents