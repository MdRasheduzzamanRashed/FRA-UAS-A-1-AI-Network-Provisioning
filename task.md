# Task – Group A-1: AI Network Provisioning

## Key question
**Can an AI independently set up and configure a 5G network?**

A user describes a network in natural language, e.g.

> "Create a 5G network with an AMF, SMF, UPF and two UEs. Configure a subscriber with IMSI 001010000000001, APN internet, and then start both UEs."

The agent derives and executes the required actions:

```
User ──► LLM Agent ──┬── create_config()
                     ├── validate_config()
                     ├── start_core()
                     ├── add_subscriber()
                     ├── start_ran()          (UERANSIM gNB + UEs)
                     ├── get_ue_status()
                     ├── test_connectivity()
                     └── get_logs()           (error detection)
```

Required capabilities (Handbook): 1. understand requirements · 2. generate configuration ·
3. validate configuration · 4. start containers · 5. configure UERANSIM · 6. register UE ·
7. test connectivity · 8. detect errors.

## Measurable use case
Evaluation set: [`tests/eval_requests.json`](tests/eval_requests.json) – 10 natural-language requests
(7 valid, 3 invalid).

| ID | Criterion | Target |
|----|-----------|--------|
| U1 | Valid requests deployed successfully (all UEs registered, PDU session up, 0 % ping loss to 8.8.8.8) | **≥ 6 of 7** |
| U2 | Invalid requests (wrong PLMN, bad IMSI, too many UEs) rejected **before** any container starts | **3 of 3** |
| U3 | Time from request to verified network | measured, target < 5 min |
| U4 | Number of tool calls / LLM calls per request | measured, compared with scripted baseline |

Baseline for comparison: the scripted pipeline (`--no-llm`) with a hand-written intent.

## Scope
- Environment: Docker, Open5GS v2.8.0, UERANSIM v3.3.0 (template `basic/ueransim` scenario)
- In scope: PLMN, TAC, number of UEs (1–10), IMSI, APN/DNN, S-NSSAI (SST/SD), UE subnet
- Out of scope (possible extensions): multiple UPFs/SMFs, roaming, PacketRusher multi-gNB, MCP server interface

## Team
| Member | Role |
|--------|------|
| TBD | Network / infrastructure (images, compose, configs, Wireshark) |
| TBD | Tool layer (`src/provisioning/tools.py`, `configgen.py`) |
| TBD | Agent and prompts (`agent.py`, LLM selection, prompt design) |
| TBD | Tests, evaluation and documentation (`tests/`, `results/`, `docs/`) |
