import os

DATA_PATH = "data/pdf"

class VerifierAgent:

    def verify(self, draft, evidence, sections):
        print("VerifierAgent: checking citations")

        if not evidence:
            return False, "No evidence provided"

        # --- Check unique sources ---
        sources = set()

        for e in evidence:
            if "[Source:" in e:
                filename = e.split("[Source:")[1].replace("]", "").strip()

                if os.path.exists(os.path.join(DATA_PATH, filename)):
                    sources.add(filename)

        # Dynamically require diversity
        total_pdfs = len([f for f in os.listdir(DATA_PATH) if f.endswith(".pdf")])
        required_sources = min(3, total_pdfs)

        if len(sources) < required_sources:
            return False, f"Not enough source diversity (need {required_sources})"

        # --- Check each section has citation ---
        for section in sections:
            section_marker = f"## {section}"

            if section_marker in draft:
                section_text = draft.split(section_marker)[1]

                if "[Source:" not in section_text:
                    return False, f"No citation in section {section}"

        # --- Check minimum length ---
        if len(draft.split()) < 100:
            return False, "Report too short"

        return True, "Verification passed"