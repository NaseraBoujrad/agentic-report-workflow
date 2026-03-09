import argparse
from tools import retrieve_documents
from verifier_agent import VerifierAgent

MAX_ITERATIONS = 8


def plan(state):
    print("Planning...")

    goal = state["goal"].lower()

    sections = []

    if "ethic" in goal:
        sections.append("Ethical concerns")
    if "healthcare" in goal:
        sections.append("Healthcare applications")
    if "analytics" in goal:
        sections.append("Predictive analytics use cases")

    if not sections:
        sections = ["Overview", "Implications", "Challenges"]

    # Only initialize once
    if state["plan"] is None:
        state["plan"] = {
            "sections": sections,
            "required_evidence_per_section": 1
        }
    else:
        # Update sections but keep evidence requirement
        state["plan"]["sections"] = sections

    print(f"Plan created: {state['plan']}")


def retrieve(state):
    section_keywords = {
        "Ethical concerns": ["ethics", "bias", "fairness", "privacy", "accountability"],
        "Healthcare applications": ["diagnostic", "clinical", "radiology", "treatment", "medical"],
        "Predictive analytics use cases": ["predictive", "analytics", "risk model", "forecast"]
    }

    all_results = []

    # 1️⃣ Samla evidence per section
    for section in state["plan"]["sections"]:
        keywords = section_keywords.get(section, [])

        section_results = retrieve_documents(
            state["goal"],
            extra_keywords=keywords
        )

        all_results.extend(section_results)

    # 2️⃣ Enforce source diversity (max 2 per source)
    unique_sources = {}
    diversified_results = []

    for item in all_results:
        if "[Source:" not in item:
            continue

        source = item.split("[Source:")[1].replace("]", "").strip()

        if source not in unique_sources:
            unique_sources[source] = 0

        if unique_sources[source] < 2:
            diversified_results.append(item)
            unique_sources[source] += 1

    state["evidence"] = diversified_results[:12]

def generate(state):
    print("Generating draft...")

    if state["iteration"] == 1:
        state["draft"] = f"Report about {state['goal']} (no citations yet)."
        return

    sections = state["plan"]["sections"]
    evidence = state["evidence"]
    required = state["plan"]["required_evidence_per_section"]

    draft_parts = [f"Report about {state['goal']}:\n"]

    # Group evidence by source
    source_groups = {}
    for citation in evidence:
        source = citation.split("[Source:")[1].replace("]", "").strip()
        source_groups.setdefault(source, []).append(citation)

    sources = list(source_groups.keys())

    source_index = 0

    for section in sections:
        draft_parts.append(f"\n## {section}\n")

        added = 0

        while added < required and sources:
            current_source = sources[source_index % len(sources)]

            if source_groups[current_source]:
                draft_parts.append(source_groups[current_source].pop(0))
                added += 1

            source_index += 1

        if added == 0:
            draft_parts.append("Insufficient evidence.")

    state["draft"] = "\n".join(draft_parts)
    
def verify(state, verifier):
    passed, reason = verifier.verify(
        state["draft"],
        state["evidence"],
         state["plan"]["sections"]
    )
    state["verification_passed"] = passed
    state["verification_reason"] = reason
    
    if passed:
        print(f"Verification passed because: {reason}")
    else:
        print(f"Verification failed because: {reason}")

def reflect(state):
    print("Reflecting on failure...")

    reason = state["verification_reason"]

    if "source diversity" in reason:
        state["plan"]["required_evidence_per_section"] += 1

    elif "too short" in reason:
        state["plan"]["required_evidence_per_section"] += 1

    elif "No citation in section" in reason:
        state["plan"]["required_evidence_per_section"] += 1

    else:
        # fallback
        state["plan"]["required_evidence_per_section"] += 1

def run_agent(prompt: str):
    state = {
        "goal": prompt,
        "iteration": 0,
        "plan": None,
        "evidence": [],
        "draft": None,
        "verification_passed": False,
    }

    print(f"\nStarting agent for: {prompt}\n")
    verifier = VerifierAgent()

    while state["iteration"] < MAX_ITERATIONS:
        state["iteration"] += 1
        print(f"--- Iteration {state['iteration']} ---")

        plan(state)
        retrieve(state)
        generate(state)
        verify(state, verifier)

        if state["verification_passed"]:
            print("\nSuccess: Verification passed.\n")
            return state

        print("Verification failed. Revising...\n")

        reflect(state)

    print("Failure: Maximum iterations reached.")
    return state
  
def run_baseline(prompt: str):
    print(f"\nRunning BASELINE for: {prompt}\n")

    state = {
        "goal": prompt,
        "plan": f"Create report about {prompt}",
        "evidence": retrieve_documents(prompt),
        "draft": None,
    }

    # Naive generation (no iteration, no verification)
    state["draft"] = f"Report about {prompt} (no validation performed)."

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
    parser.add_argument("--prompt", type=str, required=True)
    parser.add_argument("--mode", type=str, default="agent", choices=["agent", "baseline", "eval"])
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
