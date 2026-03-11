import os

DATA_PATH = "data/pdf"

class VerifierAgent:

    def verify(self, draft, evidence, sections):
        print("VerifierAgent: checking citations")

        if not evidence:
            return False, "No evidence provided"

        # --- Check unique sources from evidence directly ---
        sources = set()
        for e in evidence:
            if "[Source:" in e:
                filename = e.split("[Source:")[1].split("]")[0].strip().lower()
                sources.add(filename)

        total_pdfs = len([f.lower() for f in os.listdir(DATA_PATH) if f.endswith(".pdf")])
        required_sources = max(2, int(total_pdfs * 0.6))

        if len(sources) < required_sources:
            return False, f"Not enough source diversity (need {required_sources}, found {len(sources)})"

        # --- Check each section has citation ---
        for section in sections:
            section_marker = f"## {section}"
            if section_marker in draft:
                section_parts = draft.split(section_marker)
                if len(section_parts) > 1:
                    section_text = section_parts[1].split("##")[0]
                    if "[Source:" not in section_text:
                        return False, f"No citation in section {section}"

        # --- Check minimum length ---
        if len(draft.split()) < 300:
            return False, "Report too short"

        return True, "Verification passed"