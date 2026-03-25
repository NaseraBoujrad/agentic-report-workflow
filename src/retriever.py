import re

CHUNK_SIZE = 200


def chunk_text(text):
    words = text.split()
    chunks = []

    for i in range(0, len(words), CHUNK_SIZE):
        chunk = " ".join(words[i:i + CHUNK_SIZE])
        chunks.append(chunk)

    return chunks


def build_index(documents):
    index = []

    for doc in documents:
        chunks = chunk_text(doc["text"])

        for chunk in chunks:
            index.append({
                "text": chunk,
                "source": doc["filename"]
            })

    print("Total chunks:", len(index))
    return index


def retrieve(index, query, k=10):
    keywords = query.lower().split()

    scored = []

    for item in index:
        text = item["text"].lower()

        score = sum(text.count(word) for word in keywords)

        if score > 0:
            scored.append((score, item))
        #else:
            # allow weak matches
        #    scored.append((0.01, item))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, item in scored[:k]:
        results.append(f"{item['text']} [Source: {item['source']}]")

    return results