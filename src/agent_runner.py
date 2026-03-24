import argparse
import random
import re

from tools import retrieve_documents
from verifier_agent import VerifierAgent
from langchain_community.chat_models import ChatOllama

llm = ChatOllama(model="llama3")

MAX_ITERATIONS = 8


def clean_sections(raw):
    raw = raw.replace("Here are the suggested report section titles:", "")
    raw = raw.replace("Here are the section titles:", "")
    raw = raw.replace("Sections:", "")
    parts = re.split(r",|\n", raw)
    sections = [p.strip() for p in parts if len(p.strip()) > 2]
    return sections[:5]


def extract_source(sentence):
    if "[Source:" not in sentence:
        return None
    return sentence.split("[Source:")[1].split("]")[0].strip()


def plan(state):

    print("Planning with LLM...")

    if state["plan"] is not None:
        return

    retry_note = ""
    if state.get("plan_retry"):
        retry_note = "Your previous plan was invalid (too few sections). Fix it."

    prompt = f"""
    The user goal is: {state['goal']}.

    {retry_note}

    Create a structured research plan.

    Return JSON with:
    - sections: list of 3-6 section titles
    - required_evidence_per_section: integer (2-5)
    - max_per_source: integer (1-3)

    Example:
    {{
        "sections": ["Overview", "Applications", "Challenges"],
        "required_evidence_per_section": 3,
        "max_per_source": 2
    }}
    """

    response = llm.invoke(prompt)

    try:
        content = response.content.strip()

        # crude JSON extraction (works surprisingly well)
        json_str = re.search(r"\{.*\}", content, re.DOTALL).group(0)

        parsed = eval(json_str)

        sections = parsed.get("sections", [])

        if len(sections) < 3:
            state["plan_retry"] = True
            return

        state["plan"] = {
            "sections": sections,
            "required_evidence_per_section": int(parsed.get("required_evidence_per_section", 3)),
            "max_per_source": int(parsed.get("max_per_source", 2))
        }

        print("Plan created:", state["plan"])

    except Exception as e:
        print("Plan parsing failed, retrying...", e)
        state["plan_retry"] = True


def retrieve(state):

    print("Retrieving evidence (agentic mode)...")

    sections = state["plan"]["sections"]

    # --- STEP 1: Generate queries per section ---
    query_prompt = f"""
    The goal is: {state['goal']}

    Sections:
    {sections}

    Generate 1-2 high-quality search queries per section.

    Return as JSON:
    {{
        "Section Name": ["query1", "query2"]
    }}
    """

    response = llm.invoke(query_prompt)

    try:
        json_str = re.search(r"\{.*\}", response.content, re.DOTALL).group(0)
        section_queries = eval(json_str)
    except:
        print("Query generation failed, fallback to simple queries")
        section_queries = {s: [f"{state['goal']} {s}"] for s in sections}

    all_results = []

    # --- STEP 2: Retrieve per section ---
    for section, queries in section_queries.items():

        for q in queries:
            print(f"Querying: {q}")
            results = retrieve_documents(q)

            # tag results with section (lightweight context)
            for r in results:
                all_results.append((section, r))

    # --- STEP 3: Source diversification ---
    max_per_source = state["plan"]["max_per_source"]

    source_counts = {}
    diversified = []

    for section, item in all_results:

        src = extract_source(item)
        if not src:
            continue

        source_counts.setdefault(src, 0)

        if source_counts[src] < max_per_source:
            diversified.append(item)
            source_counts[src] += 1

    # --- STEP 4: Deduplicate ---
    seen = set()
    deduped = []

    for item in diversified:
        if item not in seen:
            deduped.append(item)
            seen.add(item)

    # --- STEP 5: Adaptive target ---
    sections_count = len(sections)
    required = state["plan"]["required_evidence_per_section"]
    target = sections_count * required

    state["evidence"] = deduped[:target]

    sources = {extract_source(e) for e in state["evidence"]}

    print("Evidence count:", len(state["evidence"]))
    print("Sources used:", sources)

    # --- STEP 6: Adaptive retry if weak ---
    if len(state["evidence"]) < target:
        print("Not enough evidence, expanding queries...")

        expansion_prompt = f"""
        The current evidence is insufficient.

        Goal: {state['goal']}

        Generate broader or alternative search queries.
        Return as a list.
        """

        response = llm.invoke(expansion_prompt)

        extra_queries = re.split(r"\n|,", response.content)

        for q in extra_queries:
            q = q.strip()
            if len(q) < 5:
                continue

            print(f"Expanding query: {q}")
            results = retrieve_documents(q)

            for r in results:
                if r not in state["evidence"]:
                    state["evidence"].append(r)

            if len(state["evidence"]) >= target:
                break


def distribute_evidence(sections, evidence):

    print("Assigning evidence to sections using LLM...")

    prompt = f"""
    You are organizing research evidence.

    Sections:
    {sections}

    Evidence:
    {evidence}

    Assign each evidence sentence to the most relevant section.

    Return JSON like:
    {{
        "Section Name": ["evidence1", "evidence2"]
    }}
    """

    response = llm.invoke(prompt)

    try:
        json_str = re.search(r"\{.*\}", response.content, re.DOTALL).group(0)
        section_map = eval(json_str)

        # fallback safety (in case LLM skips sections)
        for s in sections:
            if s not in section_map:
                section_map[s] = []

        return section_map

    except Exception as e:
        print("LLM evidence assignment failed, falling back...", e)

        #fallback to old rule-based logic
        evidence_per_section = max(1, len(evidence) // len(sections))

        section_map = {}
        idx = 0

        for s in sections:
            section_map[s] = evidence[idx: idx + evidence_per_section]
            idx += evidence_per_section

        return section_map


def generate(state):

    print("Generating draft with LLM...")

    sections = state["plan"]["sections"]
    evidence = state["evidence"]

    section_evidence = distribute_evidence(sections, evidence)

    allowed_sources = list({extract_source(e) for e in evidence})

    prompt = f"""
    You are writing a scientific research report.

    Goal:
    {state['goal']}

    Structure:
    Use the provided section titles. Each section should have a clear heading:

    ## Section Name

    Writing Guidelines:

    - Use the provided evidence where relevant
    - Each section should include at least one citation when possible
    - Prefer citing from these sources:
      {allowed_sources}
    - Citations should follow this format:
      [Source: filename.pdf]

    Sections to write:
    {sections}

    Evidence available:
    """

    for sec, ev in section_evidence.items():

        prompt += f"\nEvidence for '{sec}':\n"

        for e in ev:
            prompt += f"- {e}\n"

    prompt += """
    Write a coherent, well-structured report.
    Use evidence naturally, not mechanically.
    """

    response = llm.invoke(prompt)

    state["draft"] = response.content
    state["draft_history"].append(response.content)

    state["needs_verification"] = True


def verify(state, verifier):

    print("VerifierAgent: checking report")

    draft = state["draft"]
    evidence = state["evidence"]

    allowed_sources = {extract_source(e) for e in evidence}

    citations = re.findall(r"\[Source:(.*?)\]", draft)

    for c in citations:

        if c.strip() not in allowed_sources:
            state["verification_passed"] = False
            state["verification_reason"] = "Hallucinated citation detected"
            state["needs_verification"] = False
            print("Verification failed: hallucinated citation")
            return

    passed, reason = verifier.verify(
        draft,
        evidence,
        state["plan"]["sections"]
    )

    state["verification_passed"] = passed
    state["verification_reason"] = reason
    state["needs_verification"] = False

    print("Draft word count:", len(draft.split()))
    print(f"Verification {'passed' if passed else 'failed'}:", reason)


def reflect(state):

    print("Reflecting with LLM...")

    prompt = f"""
    The report failed verification.

    Reason:
    {state['verification_reason']}

    Current plan:
    {state['plan']}

    Current evidence count:
    {len(state['evidence'])}

    Suggest improvements.

    You may update:
    - required_evidence_per_section
    - max_per_source
    - whether new retrieval is needed (set "retrieve_more": true/false)

    Return JSON:
    {{
        "required_evidence_per_section": int,
        "max_per_source": int,
        "retrieve_more": true/false
    }}
    """

    response = llm.invoke(prompt)

    try:
        json_str = re.search(r"\{.*\}", response.content, re.DOTALL).group(0)
        updates = eval(json_str)

        if "required_evidence_per_section" in updates:
            state["plan"]["required_evidence_per_section"] = int(
                updates["required_evidence_per_section"]
            )

        if "max_per_source" in updates:
            state["plan"]["max_per_source"] = int(
                updates["max_per_source"]
            )

        if updates.get("retrieve_more"):
            print("LLM decided to retrieve more evidence")
            state["evidence"] = []

        print("Updated plan after reflection:", state["plan"])

    except Exception as e:
        print("Reflection parsing failed, doing minimal fallback...", e)

        #minimal fallback so that it doesnt stall forever
        state["plan"]["required_evidence_per_section"] += 1


def choose_tool(state):

    if not state["evidence"]:
        print("Routing: retrieve_documents")
        return "retrieve_documents"

    if state["needs_verification"]:
        print("Routing: verify_report")
        return "verify_report"

    if state["draft"] and not state["verification_passed"]:
        print("Routing: regenerate")
        return "generate_report"

    if state["verification_passed"]:
        print("Routing: finish")
        return "finish"

    return "generate_report"


def run_agent(prompt: str):

    state = {
        "goal": prompt,
        "iteration": 0,
        "plan": None,
        "evidence": [],
        "draft": None,
        "draft_history": [],
        "verification_passed": False,
        "verification_reason": "",
        "min_words_per_section": 80,
        "needs_verification": False
    }

    print(f"\nStarting agent for: {prompt}\n")

    verifier = VerifierAgent(llm)
    while state["iteration"] < MAX_ITERATIONS:

        state["iteration"] += 1

        print(f"\n--- Iteration {state['iteration']} ---")

        plan(state)

        tool = choose_tool(state)

        if tool == "retrieve_documents":

            retrieve(state)

        elif tool == "generate_report":

            generate(state)

        elif tool == "verify_report":

            verify(state, verifier)

            if not state["verification_passed"]:
                reflect(state)

        elif tool == "finish":

            print("\nAgent finished successfully.\n")
            print(state["draft"])
            return state

    print("\nMaximum iterations reached.")

    return state


def run_baseline(prompt: str):

    print(f"\nRunning BASELINE for: {prompt}\n")

    state = {
        "goal": prompt,
        "plan": f"Create report about {prompt}",
        "evidence": retrieve_documents(prompt),
        "draft": f"Report about {prompt} (no validation performed)."
    }

    print("\nBaseline finished.\n")

    return state


def evaluate(prompts: list):

    print("\nRunning evaluation...\n")

    total_iterations = 0
    agent_success = 0

    for prompt in prompts:

        print(f"\n=== Prompt: {prompt} ===")

        agent_state = run_agent(prompt)

        if agent_state.get("verification_passed"):
            agent_success += 1

        total_iterations += agent_state["iteration"]

    print("\nEvaluation results:")

    print(f"Agent success rate: {agent_success}/{len(prompts)}")
    print(f"Average iterations: {total_iterations / len(prompts)}")


if __name__ == "__main__":

    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--prompt",
        type=str,
        required=True
    )

    parser.add_argument(
        "--mode",
        type=str,
        default="agent",
        choices=["agent", "baseline", "eval"]
    )

    args = parser.parse_args()

    if args.mode == "agent":

        final_state = run_agent(args.prompt)

        print("\nFinal state:")
        print(final_state)

    elif args.mode == "baseline":

        final_state = run_baseline(args.prompt)

        print("\nFinal state:")
        print(final_state)

    else:

        test_prompts = [
            "AI healthcare",
            "AI ethics",
            "predictive analytics healthcare"
        ]

        evaluate(test_prompts)