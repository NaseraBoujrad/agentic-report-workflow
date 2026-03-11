from pdf_loader import load_all_pdfs
import re


documents = load_all_pdfs()

def retrieve_documents(goal: str, extra_keywords=None):
    base_keywords = goal.lower().split()
    keywords_extra = extra_keywords if extra_keywords else []

    section_keywords = {
        "Ethical concerns": ["ethics", "bias", "fairness", "accountability", "privacy", "principle"],
        "Healthcare applications": ["clinical", "treatment", "diagnostic", "radiology", "hospital", "patient"],
        "Predictive analytics use cases": ["predictive", "analytics", "risk", "forecast", "model"]
    }

    per_section_results = {sec: [] for sec in section_keywords}

    for doc in documents:
        text = re.sub(r"\n+", " ", doc["text"])
        sentences = re.split(r'(?<=[.!?])\s+', text)
        added_from_doc = {sec: False for sec in section_keywords}

        usable_sentences = []

        for sentence in sentences:
            sentence_clean = sentence.strip()
            sentence_clean = re.sub(r"\[\d+\]", "", sentence_clean)

            # Relaxed filtering
            if len(sentence_clean.split()) < 6:
                continue
            if ";" in sentence_clean and sentence_clean.count(";") > 2:
                continue
            if any(x in sentence_clean.lower() for x in ["doi", "http", "www", "vol", "issue"]):
                continue

            usable_sentences.append(sentence_clean)

            for section, sec_keywords in section_keywords.items():
                score = sum(
                    len(re.findall(rf"\b{re.escape(word)}\b", sentence_clean.lower()))
                    for word in base_keywords + keywords_extra + sec_keywords
                )
                goal_bonus = sum(1 for word in base_keywords if word in sentence_clean.lower())
                score = (score + goal_bonus * 2) / max(len(sentence_clean.split()), 1)

                if score > 0:
                    citation = f"{sentence_clean} [Source: {doc['filename']}]"
                    per_section_results[section].append((score, citation))
                    added_from_doc[section] = True

        # FORCE at least one sentence per PDF per section
        for section, added in added_from_doc.items():
            if not added and usable_sentences:
                citation = f"{usable_sentences[0]} [Source: {doc['filename']}]"
                per_section_results[section].append((0.01, citation))

    # Take top N per section
    for section in per_section_results:
        per_section_results[section].sort(key=lambda x: x[0], reverse=True)
        per_section_results[section] = [c[1] for c in per_section_results[section][:20]]

    # Interleave for final results
    final_results = []
    section_names = list(per_section_results.keys())
    index = 0
    while len(final_results) < 50:
        added_any = False
        for section in section_names:
            if index < len(per_section_results[section]):
                final_results.append(per_section_results[section][index])
                added_any = True
        if not added_any:
            break
        index += 1

    # Show which PDFs actually contributed
    contributing_sources = set()
    for s in final_results:
        if "[Source:" in s:
            contributing_sources.add(s.split("[Source:")[1].split("]")[0].strip())
    print(f"PDFs contributing to evidence: {contributing_sources}")

    return final_results