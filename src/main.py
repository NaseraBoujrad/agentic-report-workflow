import argparse
from langchain_ollama import ChatOllama

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


def generate(goal, sections, evidence):
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
    - Include at least ONE [Source: ...] citation

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
    

    If you break these rules, the output is invalid.

    Examples of correct citations:

    Correct: AI improves diagnostics [Source: ethical_ai_healthcare_review.pdf]

    Incorrect: Privacy is important in healthcare. [1] 
    Incorrect: AI has challenging ethical problems. (Smith, 2020)
    Incorrect: With AI on the rise it is more important than ever to implement it. [1: file.pdf]
    """

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

        draft = generate(goal, sections, evidence)

    print("\n--- FINAL REPORT ---\n")
    print(draft)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()

    parser.add_argument("--prompt", type=str, required=True)

    args = parser.parse_args()

    run_agent(args.prompt)