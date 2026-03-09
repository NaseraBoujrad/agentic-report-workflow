from pdf_loader import load_all_pdfs
import re

def retrieve_documents(goal: str, extra_keywords=None):

    documents = load_all_pdfs()
    base_keywords = goal.lower().split()
    keywords = base_keywords + extra_keywords if extra_keywords else base_keywords

    per_source_results = {}

    for doc in documents:
        text = re.sub(r"\n+", " ", doc["text"])
        sentences = re.split(r"(?<=[.!?])\s+", text)

        scored_sentences = []

        for sentence in sentences:
            sentence_clean = sentence.strip()

            if len(sentence_clean) < 40:
                continue

            score = sum(sentence_clean.lower().count(word) for word in keywords)

            if score > 0:
                citation = f"{sentence_clean} [Source: {doc['filename']}]"
                scored_sentences.append((score, citation))

        scored_sentences.sort(key=lambda x: x[0], reverse=True)

        per_source_results[doc["filename"]] = [c[1] for c in scored_sentences[:5]]

    final_results = []
    sources = list(per_source_results.keys())

    index = 0
    while len(final_results) < 20:
        added_any = False

        for source in sources:
            if index < len(per_source_results[source]):
                final_results.append(per_source_results[source][index])
                added_any = True

        if not added_any:
            break

        index += 1

    return final_results