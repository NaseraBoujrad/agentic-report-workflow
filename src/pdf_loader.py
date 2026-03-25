import os
import pdfplumber

DATA_PATH = os.path.join(os.getcwd(), "data/pdf")


def load_pdfs():
    documents = []

    for filename in os.listdir(DATA_PATH):
        if not filename.endswith(".pdf"):
            continue

        path = os.path.join(DATA_PATH, filename)
        print("Loading:", path)

        text = ""

        try:
            with pdfplumber.open(path) as pdf:
                for page in pdf.pages:
                    page_text = page.extract_text()
                    if page_text:
                        text += page_text + "\n"

        except Exception as e:
            print("Failed:", filename, e)
            continue

        if text.strip():
            documents.append({
                "filename": filename,
                "text": text
            })

    print("Loaded PDFs:", len(documents))
    return documents