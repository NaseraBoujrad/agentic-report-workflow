import os
from pypdf import PdfReader

DATA_PATH = "data/pdf"

def load_all_pdfs():
    documents = []

    for filename in os.listdir(DATA_PATH):
        if filename.endswith(".pdf"):
            path = os.path.join(DATA_PATH, filename)
            reader = PdfReader(path)

            full_text = ""
            for page in reader.pages:
                text = page.extract_text()
                if text:
                    full_text += text + "\n"

            documents.append({
                "filename": filename,
                "text": full_text
            })

    return documents