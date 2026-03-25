import re


def verify(draft, evidence, planned_sections=None):
    import re

    # Extract all cited sources from draft
    cited_sources = re.findall(r"\[Source: ([^\]]+)\]", draft)
    cited_sources_set = set(cited_sources)

    # Check each section has at least one citation
    sections_ok = True
    section_headers = re.findall(r"## ([^\n]+)", draft)
    for header in section_headers:
        # Find the section text
        pattern = rf"## {re.escape(header)}(.*?)(?=## |$)"
        match = re.search(pattern, draft, flags=re.DOTALL)
        if match:
            section_text = match.group(1)
            if "[Source:" not in section_text:
                sections_ok = False
                break
        else:
            sections_ok = False
            break

    # Check that all cited sources are actually in evidence (no hallucination)
    evidence_sources = set(
        e.split("[Source:")[1].split("]")[0].strip()
        for e in evidence if "[Source:" in e
    )
    sources_ok = cited_sources_set.issubset(evidence_sources)

    # Optional: ensure all planned sections exist in draft
    sections_match = True
    if planned_sections:
        sections_match = all(sec in section_headers for sec in planned_sections)

    passed = sections_ok and sources_ok and sections_match
    reason = "OK" if passed else "Failed verification: "
    if not sections_ok:
        reason += "Some sections missing citations. "
    if not sources_ok:
        reason += "Some cited sources not in evidence. "
    if not sections_match:
        reason += "Draft sections do not match planned sections."

    return passed, reason