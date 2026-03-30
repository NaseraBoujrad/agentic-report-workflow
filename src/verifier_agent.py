import os
import re

DATA_PATH = "../data/pdf"

class VerifierAgent:

    def verify(self, draft, evidence, sections):
        print("Verifier: checking...")

        if not evidence:
            return False, "No evidence"

        # --- Collect sources (case insensitive) ---
        sources = set()
        for e in evidence:
            if "[source:" in e.lower():
                try:
                    filename = e.lower().split("[source:")[1].split("]")[0].strip()
                    sources.add(filename)
                except:
                    continue

        total_pdfs = len([
            f.lower() for f in os.listdir(DATA_PATH) if f.endswith(".pdf")
        ])

        required_sources = max(2, int(total_pdfs * 0.4))

        if len(sources) < required_sources:
            return False, f"Low source diversity ({len(sources)}/{required_sources})"

        # --- Check each section exists + has citation ---
        for section in sections:
            marker = f"## {section}"

            if marker not in draft:
                return False, f"Missing section: {section}"

            try:
                part = draft.split(marker)[1]
                next_split = part.split("##")
                part = next_split[0] if len(next_split) > 0 else part
            except:
                return False, f"Parsing error in {section}"

            if "[source:" not in part.lower():
                return False, f"No citation in {section}"

        # --- Length check ---
        if len(draft.split()) < 200:
            return False, "Too short"

        return True, "Passed"