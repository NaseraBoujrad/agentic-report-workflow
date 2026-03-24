import os
import re

DATA_PATH = os.getcwd() + "/data/pdf"

class VerifierAgent:

    def __init__(self, llm):
        self.llm = llm

    def verify(self, draft, evidence, sections):

        print("VerifierAgent: running hybrid verification")

        if not evidence:
            return False, "No evidence provided"

        # ----------------------------
        # 1. Extract sources from evidence
        # ----------------------------
        sources = set()
        for e in evidence:
            if "[Source:" in e:
                filename = e.split("[Source:")[1].split("]")[0].strip().lower()
                sources.add(filename)

        total_pdfs = len([
            f.lower() for f in os.listdir(DATA_PATH)
            if f.endswith(".pdf")
        ])

        required_sources = max(2, int(total_pdfs * 0.3))  # slightly relaxed

        if len(sources) < required_sources:
            return False, f"Not enough source diversity (need {required_sources}, found {len(sources)})"

        # ----------------------------
        # 2. Basic structure checks
        # ----------------------------
        for section in sections:
            section_marker = f"## {section}"

            if section_marker not in draft:
                return False, f"Missing section: {section}"

            section_parts = draft.split(section_marker)
            if len(section_parts) > 1:
                section_text = section_parts[1].split("##")[0]

                if "[Source:" not in section_text:
                    return False, f"No citation in section {section}"

        # ----------------------------
        # 3. Minimum length check
        # ----------------------------
        if len(draft.split()) < 300:
            return False, "Report too short"

        # ----------------------------
        # 4. LLM-based semantic verification
        # ----------------------------
        print("VerifierAgent: running LLM semantic check")

        prompt = f"""
        You are verifying a scientific report.

        Report:
        {draft}

        Evidence:
        {evidence}

        Sections:
        {sections}

        Evaluate the following:

        1. Are claims supported by the provided evidence?
        2. Are citations used correctly and not hallucinated?
        3. Is the report logically consistent and coherent?
        4. Is evidence actually used meaningfully (not just inserted)?

        If everything is acceptable, return:

        PASS

        Otherwise return:

        FAIL: <short reason>
        """

        response = self.llm.invoke(prompt)
        result = response.content.strip()

        if result.startswith("PASS"):
            return True, "Verification passed"

        if result.startswith("FAIL"):
            reason = result.replace("FAIL:", "").strip()
            return False, reason

        # fallback (LLM being weird as usual)
        return False, "Unclear verification result"