# Architecture

## Overview

```
┌────────────────────┐
│ User (natural      │  "Create a 5G network with two UEs ..."
│ language)          │
└─────────┬──────────┘
          ▼
┌────────────────────┐   OpenAI-compatible chat API with tool calling
│ LLM Agent          │   (local Ollama by default, cloud model optional)
│ src/provisioning/  │
│ agent.py           │
└─────────┬──────────┘
          │ tool calls (JSON)
          ▼
┌──────────────────────────────────────────────────────────┐
│ Tool layer  src/provisioning/tools.py                    │
│  create_config · validate_config · start_core            │
│  add_subscriber · start_ran · get_ue_status              │
│  test_connectivity · get_logs · get_network_status       │
│  teardown                                                │
│  - fixed commands only, no shell, container allow-list   │
└───────┬───────────────────────┬──────────────────────────┘
        │                       │
        ▼                       ▼
┌────────────────┐     ┌──────────────────────────────┐
│ configgen.py   │     │ docker compose / docker exec │
│ intent → YAML  │     │ open5gs-dbctl (MongoDB)      │
│ + validation   │     └──────────────┬───────────────┘
└────────────────┘                    ▼
             ┌─────────────────────────────────────────────┐
             │ Open5GS core (NRF AMF SMF UPF AUSF UDM UDR  │
             │ PCF NSSF BSF + MongoDB)  ◄─N2/N3─►          │
             │ UERANSIM gNB  ◄──►  ue1 … ueN               │
             └─────────────────────────────────────────────┘
```

## Design decisions
1. **Intent, not files.** The LLM fills in a structured `NetworkIntent` (JSON). Python code
   generates the YAML files from the template's working `basic/ueransim` scenario. This avoids
   hallucinated config keys and keeps the result close to a known-good configuration.
2. **Validate before start.** `validate_config` checks cross-file consistency
   (PLMN in AMF/gNB/UE, TAC, S-NSSAI in AMF/NSSF/gNB/UE, SMF/UPF subnet, gNB→AMF address,
   compose file references). Containers are only started with a valid configuration.
3. **Least privilege.** The agent cannot run arbitrary commands. Every tool executes a fixed
   command with validated arguments, and only on containers of the current network.
4. **Verification from the network itself.** Success is decided from UERANSIM logs
   (registration, PDU session, TUN IP) and a ping through `uesimtun0`, not from the LLM's opinion.
5. **Scripted baseline.** The same tools run in fixed order without an LLM (`--no-llm`), which
   gives a reference for success rate, time and number of steps.

## Possible extension
Expose the tools as an MCP server (cf. Group 5 – MCP Network Controller) so that any
MCP-capable client can provision the network.
