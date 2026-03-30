import os
import pdfplumber
import pytesseract
import re

DATA_PATH = "../data/pdf"


def clean_text(text):
    text = re.sub(r"\n+", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def load_all_pdfs():
    documents = []

    for filename in os.listdir(DATA_PATH):
        if not filename.endswith(".pdf"):
            continue

        path = os.path.join(DATA_PATH, filename)
        print("Loading:", path)

        full_text = ""

        try:
            with pdfplumber.open(path) as pdf:
                for i, page in enumerate(pdf.pages):

                    text = page.extract_text()

                    if text and text.strip():
                        full_text += text + "\n"

                    else:
                        print(f"OCR fallback on page {i} ({filename})")

                        try:
                            image = page.to_image(resolution=300).original  # 🔥 bättre OCR
                            ocr_text = pytesseract.image_to_string(image)

                            if ocr_text.strip():
                                full_text += ocr_text + "\n"

                        except Exception as e:
                            print(f"OCR failed on page {i}: {e}")

        except Exception as e:
            print(f"Failed to open {filename}: {e}")
            continue

        full_text = clean_text(full_text)

        #  säkerställ att dokument inte är skräp
        if len(full_text.split()) > 50:
            documents.append({
                "filename": filename,
                "text": full_text
            })
        else:
            print(f"No usable text from {filename}")

    print("Total PDFs loaded:", len(documents))

    return documents