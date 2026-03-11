# agentic-report-workflow
Agentic workflow system that generates and verifies document based reports using iterative planning, tool use, and validation.
# Overview
A simple Python project that generates reports on a given topic using PDF sources. 
Supports two modes: **baseline** (direct evidence retrieval) and **agent** (structured, verified draft generation).

This project implements an agentic workflow that generates structured reports from local documents. 
The system uses iterative planning, tool calls, validation, and recovery to ensure that all citations in the report are grounded in source documents.


## Requirements

- Python 3.13.5+
- PyPdf
- PyTesseract

## Usage

Run the agent or baseline mode with a prompt:

## Baseline mode
python src/agent_runner.py --prompt "AI healthcare ethics" --mode baseline

## Agent mode
python src/agent_runner.py --prompt "AI healthcare ethics" --mode agent






# Task Definition
The goal is to generate a report about a given topic using only locally stored documents.
The agent:

- Searches documents

- Extracts candidate quotes

- Generates a report

- Verifies that all quotes exist in the source documents

- Iterates if verification fails

The task succeeds when all citations are verified and the report meets defined constraints within a maximum number of iterations.

# Inputs

- User prompt (report topic)

- Local document corpus (docs/)

# Actions

The agent can:

- Search documents

- Extract candidate quotes

- Generate report sections

- Verify citations against source documents

- Revise the report if verification fails

# Environment Dynamics

- Each tool call updates the internal state:

- Retrieval updates the evidence pool

- Draft generation updates the report structure

- Verification produces pass/fail feedback

- Revision modifies plan and draft

# Success Criteria

The workflow succeeds if:

- The report answers the prompt

- Each claim contains at least one citation

- All citations are verified

- Maximum iteration limit is not exceeded

# Failure Criteria

- Unverified citations remain

- Maximum iterations reached

- Insufficient evidence found

- Text too short

# Constraints

- Maximum 8 iterations

- Only local documents allowed

- No external web search

- All decisions logged

# Agent
The system follows an explicit agent loop:

goal > plan > retrieve > extract > generate > verify > revise (if needed)
