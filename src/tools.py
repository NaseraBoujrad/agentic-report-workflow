from pdf_loader import load_all_pdfs
import re

documents = load_all_pdfs()

def retrieve_documents(goal: str, extra_keywords=None):
    base_keywords = goal.lower().split()
    keywords_extra = extra_keywords if extra_keywords else []

    results = []

    for doc in documents:
        text = re.sub(r"\n+", " ", doc["text"])
        sentences = re.split(r'(?<=[.!?])\s+', text)

        for sentence in sentences:
            sentence = sentence.strip()
            sentence = re.sub(r"\[\d+\]", "", sentence)

            if len(sentence.split()) < 6:
                continue

            sentence_lower = sentence.lower()

            #  bättre scoring
            score = sum(
                1 for word in base_keywords + keywords_extra
                if word in sentence_lower
            )

            #  bättre filter
            if score >= 1:
                results.append((score, sentence, doc["filename"]))

    #  sortera bästa först
    results.sort(key=lambda x: x[0], reverse=True)

    #  ta top N + skapa citation
    final_results = []
    for score, sentence, filename in results[:30]:
        citation = f"{sentence} [Source: {filename}]"
        final_results.append(citation)

    return final_results