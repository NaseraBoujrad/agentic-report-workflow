# agentic-report-workflow
Agentic workflow system that generates and verifies document based reports using iterative planning, tool use, and validation.
# Overview
This project implements an agentic workflow that generates structured reports from local documents. 
The system uses iterative planning, tool calls, validation, and recovery to ensure that all citations in the report are grounded in source documents.

# Task Definition
The goal is to generate a report about a given topic using only locally stored documents.
The agent:

-Searches documents

-Extracts candidate quotes

-Generates a report

-Verifies that all quotes exist in the source documents

-Iterates if verification fails

The task succeeds when all citations are verified and the report meets defined constraints within a maximum number of iterations.

# Architecture
The system follows an explicit agent loop:

goal → plan → retrieve → extract → generate → verify → revise (if needed)

State, tool calls, validation results, and iteration steps are logged.

# Baseline
We compare the agentic workflow to a single-prompt baseline without iterative validation.

# How to Run
pip install -r requirements.txt

python src/agent.py
