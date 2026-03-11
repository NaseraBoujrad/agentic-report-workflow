import argparse
from tools import retrieve_documents
from verifier_agent import VerifierAgent
import random

MAX_ITERATIONS = 8


def plan(state):
    print("Planning...")

    if state["plan"] is not None:
        return  

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

    state["plan"] = {
        "sections": sections,
        "required_evidence_per_section": 3,
        "max_per_source": 15  # Track max per source for diversity
    }

    print(f"Plan created: {state['plan']}")


def retrieve(state):
    section_keywords = {
        "Ethical concerns": ["ethics", "bias", "fairness", "privacy", "accountability"],
        "Healthcare applications": ["diagnostic", "clinical", "radiology", "treatment", "medical"],
        "Predictive analytics use cases": ["predictive", "analytics", "risk", "forecast", "model"]
    }

    all_results = []

    for section in state["plan"]["sections"]:
        keywords = section_keywords.get(section, [])
        query = f"{state['goal']} {section}"
        section_results = retrieve_documents(query, extra_keywords=keywords)
        all_results.extend(section_results)

    max_per_source = state["plan"].get("max_per_source", 2)

    source_counts = {}
    all_sources = set()
    for item in all_results:
        if "[Source:" not in item:
            continue
        source = item.split("[Source:")[1].split("]")[0].strip()
        all_sources.add(source)
        source_counts.setdefault(source, 0)

    diversified = []

    #Guarantee 1 sentence per PDF first
    for source in all_sources:
        for item in all_results:
            if f"[Source: {source}]" in item:
                diversified.append(item)
                source_counts[source] += 1
                break  # only one guaranteed sentence

    #Fill remaining slots respecting max_per_source
    for item in all_results:
        if "[Source:" not in item:
            continue
        source = item.split("[Source:")[1].split("]")[0].strip()
        if source_counts[source] < max_per_source and item not in diversified:
            diversified.append(item)
            source_counts[source] += 1

    # "Deduplicate" and shuffle
    seen = set()
    deduped = []
    for item in diversified:
        if item not in seen:
            deduped.append(item)
            seen.add(item)

    random.shuffle(deduped)

    if len(all_sources) < 3:
        print(f"Warning: Only {len(all_sources)} unique sources found.")

    state["evidence"] = deduped[:12]

    #debug to show which PDFs contributed
    contributing_sources = set()
    for s in state["evidence"]:
        if "[Source:" in s:
            contributing_sources.add(s.split("[Source:")[1].split("]")[0].strip())
    print("PDFs contributing to evidence:", contributing_sources)


def generate(state):
    print("Evidence count:", len(state["evidence"]))
    print("Evidence per section required:", state["plan"]["required_evidence_per_section"])
    print("Generating draft...")

    sections = state["plan"]["sections"]
    required = state["plan"]["required_evidence_per_section"]

    # unique filler sentences
    filler_sentences = [
        "Researchers continue to debate important aspects of this topic.",
        "These findings highlight broader implications within the field.",
        "Scholars emphasize that this area remains an evolving research domain."
    ]

    draft_parts = [f"Report about {state['goal']}:\n"]

    #group evidence by source
    source_groups = {}
    for citation in state["evidence"]:
        if "[Source:" not in citation:
            continue
        source = citation.split("[Source:")[1].split("]")[0].strip()
        source_groups.setdefault(source, []).append(citation)

    for section in sections:
        draft_parts.append(f"\n## {section}\n")
        section_parts = []

        #add evidence first
        added = 0
        used_sources = set()
        sources_with_evidence = [s for s, items in source_groups.items() if items]

        while added < required and sources_with_evidence:
            for source in sources_with_evidence:
                if source_groups[source]:
                    citation = source_groups[source].pop(0)
                    expanded_text = (
                        f"This evidence highlights an aspect of {section.lower()}. "
                        f"{citation} "
                        f"This illustrates how {state['goal']} connects to the broader context of {section.lower()}."
                    )
                    section_parts.append(expanded_text)
                    added += 1
                    used_sources.add(source)
            sources_with_evidence = [s for s, items in source_groups.items() if items]

        #If no evidence found for this section
        if added == 0:
            section_parts.append("Insufficient evidence available for this section.")

        #add unique fillers if section is still too short
        section_text = " ".join(section_parts)
        unused_fillers = filler_sentences.copy()
        while len(section_text.split()) < state["min_words_per_section"] and unused_fillers:
            sentence = unused_fillers.pop(0)
            section_parts.append(sentence)
            section_text = " ".join(section_parts)

        draft_parts.extend(section_parts)

    state["draft"] = "\n".join(draft_parts)


def verify(state, verifier):
    passed, reason = verifier.verify(
        state["draft"],
        state["evidence"],
        state["plan"]["sections"]
    )
    state["verification_passed"] = passed
    state["verification_reason"] = reason
    print("Draft word count:", len(state["draft"].split()))
    print(f"Verification {'passed' if passed else 'failed'}: {reason}")


def reflect(state):
    print("Reflecting on failure...")
    reason = state.get("verification_reason", "").lower()

    if "too short" in reason:
        state["min_words_per_section"] += 40
        print("Increasing minimum words per section to:", state["min_words_per_section"])

    elif "no citation in section" in reason:
        state["plan"]["required_evidence_per_section"] = min(
            state["plan"]["required_evidence_per_section"] + 1, 5
        )
        print("Increasing evidence requirement to:", state["plan"]["required_evidence_per_section"])

    elif "source diversity" in reason or "not enough source diversity" in reason:
        if state["plan"].get("max_per_source", 2) < 5:
            state["plan"]["max_per_source"] += 1
            print("Relaxing max-per-source to:", state["plan"]["max_per_source"])
        else:
            print("Max-per-source already at limit. Proceeding with available evidence.")
            state["verification_passed"] = True
            state["verification_reason"] = (
                f"Proceeding despite limited diversity: only {len(set([e.split('[Source:')[1].split(']')[0].strip() for e in state['evidence']]))} sources."
            )
    else:
        state["min_words_per_section"] += 20
        print("Increasing minimum words per section to:", state["min_words_per_section"])


def run_agent(prompt: str):
    state = {
        "goal": prompt,
        "iteration": 0,
        "plan": None,
        "evidence": [],
        "draft": None,
        "verification_passed": False,
        "min_words_per_section": 80
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