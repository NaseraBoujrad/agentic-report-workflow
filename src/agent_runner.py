import argparse
import json
import random
import re
from tools import retrieve_documents
from verifier_agent import VerifierAgent
from langchain_ollama import ChatOllama

llm = ChatOllama(model="llama3")
MAX_ITERATIONS = 8


# =========================
# POLICY (LLM decides next step)
# =========================
def policy(state):
    prompt = f"""
You are an autonomous agent controlling a workflow.

Goal:
{state["goal"]}

Current state:
- Plan exists: {state["plan"] is not None}
- Evidence count: {len(state["evidence"])}
- Draft exists: {state["draft"] is not None}
- Verification passed: {state["verification_passed"]}
- Verification reason: {state.get("verification_reason")}

Reflection (use this to improve your decision):
{state.get("reflection", "None")}

Available actions:
plan, retrieve, generate, verify, reflect, finish

Guidelines:
- If no plan you → MUST choose plan FIRST
- If plan exists and no evidence → retrieve
- If evidence exists and no draft → generate
- If draft exists → verify
- If verification fails → reflect
- If verification passed → finish

IMPORTANT:
- Avoid repeating the same action if it does not change the state
- Always move the workflow forward
- Use reflection to improve the next step

- If no plan you → MUST choose plan FIRST
- You are NOT allowed to generate without a plan
- Generating without a plan is a FAILURE

- If draft does NOT exist you → MUST choose generate
- You are NOT allowed to choose verify without a draft
- Choosing verify without a draft is a FAILURE

- If verification_passed is True → you MUST choose finish
- Continuing after verification success is a FAILURE

- If plan already exists → you MUST NOT choose plan again
- Repeating the same action multiple times is a FAILURE

Return ONLY JSON:
{{"action": "...", "reason": "..."}}
"""

    response = llm.invoke(prompt)
    text = response.content.strip()

    try:
        match = re.search(r'\{[\s\S]*?\}', text)
        if match:
            return json.loads(match.group())
    except:
        pass

    print("Policy failed → fallback")
    return {"action": "plan"}


# =========================
# EXECUTE
# =========================
def execute(action, state, verifier):

    if action == "plan":
        plan(state)

    elif action == "retrieve":
        retrieve(state)

    elif action == "generate":
        generate(state)

    elif action == "verify":
        verify(state, verifier)

    elif action == "reflect":
        reflect(state)


# =========================
# PLAN
# =========================
def plan(state):
    #  STOPPA loop
    if state["plan"] is not None:
        print("Plan already exists, skipping planning")
        return

    print("Planning...")

    prompt = f"""
Goal: {state['goal']}

Create 3–4 short section titles.

Return ONLY a comma-separated list.
Do NOT include any explanations.
Do NOT include phrases like "Here are...".
"""

    response = llm.invoke(prompt)

    #  CLEAN output
    text = response.content.strip()

    #  RENSNING
    text = re.sub(r"Here are.*?:", "", text)
    text = re.sub(r"Section Names:", "", text)
    text = text.replace("\n", "")

    sections = [s.strip() for s in text.split(",") if s.strip()]

    state["plan"] = {
        "sections": sections,
        "required_evidence_per_section": 3,
        "max_per_source": 15
    }

    print("Plan:", sections)


# =========================
# RETRIEVE
# =========================
def retrieve(state):
    print("Retrieving...")

    all_results = []

    if state["plan"] is None:
        print("No plan available")
        return

    for section in state["plan"]["sections"]:
        query = f"{state['goal']} {section}"
        results = retrieve_documents(query)
        all_results.extend(results)

    all_results = list(set(all_results))
    random.shuffle(all_results)

    state["evidence"] = all_results[:12]

    print("Evidence:", len(state["evidence"]))


# =========================
# GENERATE
# =========================
def generate(state):
    print("Generating...")

    evidence_text = "\n".join(state["evidence"])

    sections_formatted = "\n".join(
        [f"## {s}" for s in state["plan"]["sections"]]
    )

    prompt = f"""
Write a structured academic report about: {state['goal']}.

Use EXACTLY these section headers:
{sections_formatted}

STRICT RULES:
- Each section header MUST start with '## ' exactly
- Do NOT use bold or any other formatting for headers
- Do NOT skip any section

- Each section MUST include at least ONE citation in EXACT format:
  [Source: filename.pdf]

- DO NOT use numbered citations like [1], [2] [64], or [1: file.pdf]
- ONLY use [Source: filename.pdf]
- Remove citation numbers like 1, 2, 52, 53 from text
- Do NOT include numeric reference markers from PDFs
- DO NOT include a reference list
- EVERY paragraph MUST include a citation
- ONLY use the provided evidence
- Do NOT invent sources
- Do NOT use any sources not present in the evidence list
- Do NOT mention any tools, systems, or examples not present in the evidence.
- Only extract clean, relevant sentences from evidence
- Do NOT include broken, cut, or OCR-corrupted sentences
- Do NOT include broken or partial sentences
- Do NOT include a conclusion section unless explicitly specified
- Ignore noisy or incomplete sentences in evidence
- Only use clear and meaningful information
- Do NOT include author names or publication years unless explicitly present in the evidence
- Ensure each sentence is directly relevant to its section heading
- Do NOT include unrelated concepts even if they appear in the evidence
- Prefer combining information from multiple sources per section
- If evidence is insufficient, unclear, or not relevant to a section, skip that information
- Do NOT force content if no valid evidence is available
- Write 1–2 concise paragraphs per section

CRITICAL:
- The ONLY valid citation format is: [Source: filename.pdf]
- (Source: filename.pdf) is WRONG
- Any other format is invalid
If you use any citation format other than [Source: filename.pdf], the answer is incorrect.

Use this evidence:
{evidence_text}
"""

    response = llm.invoke(prompt)

    state["draft"] = response.content
    state["draft_history"].append(response.content)

    print(state["draft"])
# =========================
# VERIFY
# =========================
def verify(state, verifier):
    if state["draft"] is None:
        print("No draft → skipping verify")
        state["verification_passed"] = False
        state["verification_reason"] = "No draft"
        return

    passed, reason = verifier.verify(
        state["draft"],
        state["evidence"],
        state["plan"]["sections"]
    )

    state["verification_passed"] = passed
    state["verification_reason"] = reason

    print("Verification:", passed, reason)


# =========================
# REFLECT
# =========================
def reflect(state):
    print("Reflecting...")

    prompt = f"""
Goal: {state["goal"]}

State:
{state}

Verification failed reason:
{state.get("verification_reason")}

Explain what went wrong and what should be improved.

Be concise.
"""

    response = llm.invoke(prompt)

    state["reflection"] = response.content

    print("Reflection:", state["reflection"])

# =========================
# RUN AGENT
# =========================
def run_agent(prompt):
    state = {
        "goal": prompt,
        "iteration": 0,
        "plan": None,
        "evidence": [],
        "draft": None,
        "draft_history": [],
        "verification_passed": False,
        "verification_reason": None,
        "reflection": None,
        "last_action": None
    }

    verifier = VerifierAgent()

    print(f"\n Starting agent: {prompt}\n")

    while state["iteration"] < MAX_ITERATIONS:
        state["iteration"] += 1
        print(f"\n--- Iteration {state['iteration']} ---")

        # STOP + FINAL VERIFY
        if state["iteration"] >= MAX_ITERATIONS:
            print("Max iterations reached")

            if state["draft"] is not None and not state["verification_passed"]:
                print("Forcing final verification before stopping")
                verify(state, verifier)

            break

        # =========================
        # POLICY
        # =========================
        decision = policy(state)
        action = decision.get("action")

        # =========================
        #  FIX 1: STOP PLAN LOOP
        # =========================
        if action == "plan" and state["plan"] is not None:
            print("Plan already exists → forcing next logical step")

            if len(state["evidence"]) == 0:
                action = "retrieve"
            elif state["draft"] is None:
                action = "generate"
            else:
                action = "verify"

        # =========================
        #  VERIFY FAIL → REFLECT
        # =========================
        if action == "verify" and state["verification_passed"] is False and state["verification_reason"] is not None:
            print("Verification already failed → forcing reflect")
            action = "reflect"

        # =========================
        #  GUARD FOR INVALID ACTION
        # =========================
        if action not in ["plan", "retrieve", "generate", "verify", "reflect", "finish"]:
            print("Invalid action → fallback plan")
            action = "plan"

        print("Agent action:", action)
        
        with open("log.txt", "a") as f:
            f.write(f"{state['iteration']} | {action} | evidence={len(state['evidence'])}\n")

        # =========================
        #  VERIFY WITHOUT DRAFT
        # =========================
        if action == "verify" and state["draft"] is None:
            print("No draft → forcing generate")
            action = "generate"

        # =========================
        #  STOP REPEAT LOOP
        # =========================
        if state.get("last_action") == action and action in ["retrieve", "generate"]:
            print("Same action repeated → forcing reflect")
            action = "reflect"

        # =========================
        # REFLECT BLOCK
        # =========================
        if action == "reflect":
            reflect(state)

            decision = policy(state)
            action = decision.get("action")

            # =========================
            # STOP REFLECT LOOP
            # =========================
            if action == "reflect":
                print("Reflect loop → forcing generate")
                action = "generate"

            print("New action after reflection:", action)

        # =========================
        # FINISH
        # =========================
        if action == "finish":
            break

        # =========================
        # EXECUTE
        # =========================
        execute(action, state, verifier)

        # =========================
        #  FORCE VERIFY AFTER GENERATE
        # =========================
        if action == "generate":
            print("Enforcing verify after generate")
            verify(state, verifier)
            state["last_action"] = "verify"
            continue

        # =========================
        # UPDATE LAST ACTION
        # =========================
        state["last_action"] = action

    # =========================
    # RESULT
    # =========================
    if state["verification_passed"]:
        print("\n SUCCESS\n")
        print(state["draft"])
    else:
        print("\n FAILED")

    return state

# =========================
# BASELINE (no agent, no tools)
# =========================
def baseline(prompt):
    print("\n--- BASELINE RUN ---\n")

    response = llm.invoke(f"""
Write a structured academic report about: {prompt}.

Use 3–4 sections with headings.

Include citations if possible.
""")

    output = response.content

    print(output)

    return output
# =========================
# EVALUATION
# =========================
def evaluate():
    prompts = [
        "AI healthcare",
        "AI ethics in medicine",
        "Machine learning in diagnosis"
    ]

    agent_success = 0
    baseline_success = 0

    print("\n====================")
    print("RUNNING EVALUATION")
    print("====================\n")

    for p in prompts:
        print(f"\n### PROMPT: {p}\n")

        # --- Agent ---
        state = run_agent(p)

        if state["verification_passed"]:
            agent_success += 1

        # --- Baseline ---
        baseline_output = baseline(p)

        if "[Source:" in baseline_output:
            baseline_success += 1

    print("\n====================")
    print("RESULTS")
    print("====================")

    print(f"Agent success rate: {agent_success}/{len(prompts)}")
    print(f"Baseline (simple citation check): {baseline_success}/{len(prompts)}")
    
# =========================
# MAIN
# =========================
if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--prompt", type=str)
    parser.add_argument("--eval", action="store_true")
    args = parser.parse_args()

    if args.eval:
        evaluate()
    else:
        run_agent(args.prompt)


#required=True
