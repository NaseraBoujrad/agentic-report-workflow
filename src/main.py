import argparse
import re

from langchain_ollama import ChatOllama
from datetime import datetime
from pdf_loader import load_pdfs
from retriever import build_index, retrieve
from verifier import verify

llm = ChatOllama(model="llama3")


def plan(goal):
    print("Planning...")

    prompt = f"""
    Create 3 to 5 short section titles for a research report.

    Goal: {goal}

    STRICT RULES:
    - Each line MUST start with "-"
    - No explanations
    - No numbering
    - Only section titles

    Example:
    - Introduction
    - Applications
    - Challenges
    """

    response = llm.invoke(prompt)
    content = response.content.strip()

    print("Raw LLM output:\n", content)

    sections = []
    for line in content.split("\n"):
        line = line.strip()
        if line.startswith("-"):
            sections.append(line[1:].strip())

    #Fallback if LLM is dumb
    if len(sections) < 3:
        print("LLM failed to produce sections, using fallback...")
        sections = [
            "Introduction",
            "Applications",
            "Challenges",
            "Ethical Considerations",
            "Conclusion"
        ]
    
    return sections[:5]


def generate(goal, sections, evidence, feedback=None):
    sources = list(set(
    e.split("[Source:")[1].split("]")[0].strip()
    for e in evidence if "[Source:" in e))
    prompt = f"""
    Write a research report.

    Goal: {goal}

    Sections:
    {sections}
    Each section MUST:
    - Be at least 3-5 sentences
    - Every paragraph MUST contain at least one [Source: ...] citation
    - A section without a citation is invalid

    ONLY use these sources:
    {sources}

    Use this evidence:
    """

    evidence = trim_evidence(evidence)

    prompt += """

    STRICT CITATION RULES (MANDATORY):

    - Every section MUST include at least one citation
    - Section headers MUST use this exact format: ## Section Name.
    - Do NOT use any other formatting except those mentioned here, keep it in plaintext.
    - ONLY use this exact format: [Source: filename.pdf]
    - DO NOT use numbered citations like [1], (1), or similar.
    - DO NOT invent new citation formats.
    - DO NOT write a references section.
    - DO NOT explain citations.
    - DO NOT include any meta-commentary, notes, or explanations.
    - DO NOT write phrases like "Here is the report" or "I followed the rules".
    - DO NOT use parentheses for citations under ANY circumstance.

    If ANY rule is broken, the entire output is invalid and will be rejected.
    You MUST strictly follow ALL rules.
    """

    if feedback:
        prompt += f"\n\nIMPORTANT FEEDBACK FROM PREVIOUS FAILURE:\n{feedback}\nFix ALL issues."

    response = llm.invoke(prompt)
    return response.content

def trim_evidence(evidence, max_items=6, max_chars=300):
    trimmed = []
    for e in evidence[:max_items]:
        trimmed.append(e[:max_chars])
    return trimmed

def run_agent(goal):
    print("\n--- AGENT START ---\n")

    # 1. Load data
    docs = load_pdfs()
    index = build_index(docs)

    # 2. Plan
    sections = plan(goal)
    print("Sections:", sections)

    # 3. Retrieve
    evidence = []
    for sec in sections:
        query = f"{goal} {sec}"
        results = retrieve(index, query, k=5)
        evidence.extend(results)

    if not evidence:
        print("No evidence found, using fallback retrieval...")
        evidence = retrieve(index, goal, k=10)

    # dedupe
    evidence = list(set(evidence))

    print("Evidence collected:", len(evidence))

    # 4. Generate
    print("Generating draft...")
    draft = generate(goal, sections, evidence)

    # 5. Verify
    passed, reason = verify(draft, evidence, planned_sections=sections)

    print("\nVerification:", passed, reason)

    # 6. Simple retry
    if not passed:
        print("\nRetrying with more evidence...\n")

        extra = retrieve(index, goal, k=10)
        evidence.extend(extra)

        draft = generate(goal, sections, evidence, feedback=reason)

    print("\n--- FINAL REPORT ---\n")
    print(draft)

def evaluate_agent(prompts, runs_per_prompt=3, max_retries=5, output_file="evaluation.txt", quick=False):
    if quick:
        print("Running evaluation in quick mode - 2 prompts, 1 run each")
        prompts = prompts[:2]      # only 2 prompts
        runs_per_prompt = 1        # only 1 run each
    
    print(f"Running evaluation - {len(prompts)} prompts, {runs_per_prompt} runs each, {max_retries} retries per run")
    
    total_runs = 0
    passed_runs = 0
    retry_success = 0
    retry_attempts = 0

    total_citations = 0
    valid_citations = 0
    total_violations = 0

    docs = load_pdfs()
    index = build_index(docs)

    def count_violations(draft):
        violations = 0
        if re.search(r"\([^)]+\.pdf\)", draft):
            violations += 1
        sections = re.findall(r"## ([^\n]+)", draft)
        for sec in sections:
            pattern = rf"## {re.escape(sec)}(.*?)(?=## |$)"
            match = re.search(pattern, draft, re.DOTALL)
            if match and "[Source:" not in match.group(1):
                violations += 1
        if "Note:" in draft or "I followed" in draft:
            violations += 1
        return violations

    for prompt in prompts:
        for run_idx in range(runs_per_prompt):
            total_runs += 1
            print(f"\n=== PROMPT: {prompt} | RUN {run_idx + 1}/{runs_per_prompt} ===")
            
            # --- PLAN ---
            sections = plan(prompt)
            print("Sections:", sections)

            # --- RETRIEVE ---
            evidence = []
            for sec in sections:
                results = retrieve(index, f"{prompt} {sec}", k=5)
                evidence.extend(results)
            if not evidence:
                print("No evidence found, using fallback retrieval...")
                evidence = retrieve(index, prompt, k=10)
            evidence = list(set(evidence))
            print("Evidence collected:", len(evidence))

            # --- GENERATE WITH RETRIES ---
            draft = None
            passed = False
            last_feedback = None

            for attempt in range(max_retries + 1):  # initial + retries
                if attempt == 0:
                    draft = generate(prompt, sections, evidence)
                else:
                    print(f"Retry attempt {attempt}/{max_retries} for prompt '{prompt}'")
                    retry_attempts += 1
                    extra = retrieve(index, prompt, k=10)
                    evidence.extend(extra)
                    evidence = list(set(evidence))
                    draft = generate(prompt, sections, evidence, feedback=last_feedback)

                passed, last_feedback = verify(draft, evidence, planned_sections=sections)
                if passed:
                    if attempt > 0:
                        retry_success += 1
                        print(f"Retry SUCCESS on attempt {attempt}")
                    break
            else:
                print(f"All {max_retries} retries failed for prompt '{prompt}'")

            if passed:
                passed_runs += 1
                print("\n" + "="*60)
                print(f"CLEAN PASS | PROMPT: {prompt} | RUN: {run_idx + 1}")
                print("-"*60)
                print(draft)
                print("="*60 + "\n")
            else:
                print("\n" + "="*60)
                print(f"FINAL FAIL | PROMPT: {prompt} | RUN: {run_idx + 1}")
                print("-"*60)
                print(draft)
                print("="*60 + "\n")

            # --- CITATION METRICS ---
            cited = re.findall(r"\[Source: ([^\]]+)\]", draft)
            total_citations += len(cited)
            evidence_sources = set(
                e.split("[Source:")[1].split("]")[0].strip()
                for e in evidence if "[Source:" in e
            )
            valid = [c for c in cited if c in evidence_sources]
            valid_citations += len(valid)

            # --- VIOLATIONS ---
            total_violations += count_violations(draft)

    # --- FINAL METRICS ---
    pass_rate = passed_runs / total_runs if total_runs else 0
    retry_rate = (retry_success / retry_attempts) if retry_attempts else 0
    citation_accuracy = (valid_citations / total_citations) if total_citations else 0
    avg_violations = total_violations / total_runs if total_runs else 0

    report = f"""
    EVALUATION RESULTS
    ==================
    Timestamp: {datetime.now()}

    Total Runs: {total_runs}

    Verification Pass Rate: {pass_rate:.2%}
    Retry Success Rate: {retry_rate:.2%}
    Citation Accuracy: {citation_accuracy:.2%}
    Average Violations per Run: {avg_violations:.2f}
    """

    with open(output_file, "w", encoding="utf-8") as f:
        f.write(report)

    print(report)
    print(f"Saved to {output_file}")



if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--prompt", type=str)
    parser.add_argument("--eval", action="store_true")
    parser.add_argument("--quick", action="store_true")

    args = parser.parse_args()

    if args.eval:
        prompts = [
            "AI in healthcare",
            "AI in finance",
            "AI and privacy",
            "AI and ethics",
            "Compare AI in healthcare and finance"
        ]
        evaluate_agent(prompts, quick=args.quick)
    else:
        run_agent(args.prompt)