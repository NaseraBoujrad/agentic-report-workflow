# agentic-report-workflow
Agentic workflow system that generates and verifies document based reports using iterative planning, tool use, and validation.
# Overview
This project implements an agentic workflow that generates structured reports from local documents. 
The system uses iterative planning, tool calls, validation, and recovery to ensure that all citations in the report are grounded in source documents.

# Task Definition
The goal is to generate a report about a given topic using only locally stored documents.
The agent:

- Searches documents

-Extracts candidate quotes

-Generates a report

-Verifies that all quotes exist in the source documents

-Iterates if verification fails

The task succeeds when all citations are verified and the report meets defined constraints within a maximum number of iterations.

# Inputs

-User prompt (report topic)

-Local document corpus (docs/)

-Optional metadata (titles, tags)

# Actions

The agent can:

-Search documents

-Extract candidate quotes

-Generate report sections

-Verify citations against source documents

-Revise the report if verification fails

# Environment Dynamics

-Each tool call updates the internal state:

-Retrieval updates the evidence pool

-Draft generation updates the report structure

-Verification produces pass/fail feedback

-Revision modifies plan and draft

# Success Criteria

The workflow succeeds if:

-The report answers the prompt

-Each claim contains at least one citation

-All citations are verified

-Maximum iteration limit is not exceeded

# Failure Criteria

-Unverified citations remain

-Maximum iterations reached

-Insufficient evidence found

# Constraints

-Maximum 8 iterations

-Only local documents allowed

-No external web search

-All decisions logged

# Architecture
The system follows an explicit agent loop:

goal → plan → retrieve → extract → generate → verify → revise (if needed)

State, tool calls, validation results, and iteration steps are logged.

# Baseline
We compare the agentic workflow to a single-prompt baseline without iterative validation.

# Evaluation

We evaluate the workflow using:

-Citation accuracy (% verified citations)

-Success rate across N prompts

-Average number of iterations

-Execution time per run

We compare:

1.Single-prompt baseline (no tools, no validation)

2.Agentic workflow (planning + tools + verification loop)

# How to Run
pip install -r requirements.txt

Place documents inside /docs

Create a .env file based on .env.example

Run:
python src/agent_runner.py --prompt "Your topic here"
