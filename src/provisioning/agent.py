"""LLM provisioning agent (tool-calling loop) plus a scripted baseline.

LLM backend: any OpenAI-compatible /chat/completions endpoint with tool calling,
e.g. a local Ollama server (default) or a cloud API. Configure with:
    LLM_BASE_URL  (default http://localhost:11434/v1)
    LLM_MODEL     (default qwen2.5:7b)
    LLM_API_KEY   (default "ollama")

Usage:
    python -m src.provisioning.agent "Create a 5G network with two UEs ..."
    python -m src.provisioning.agent --intent tests/intents/two_ues.json --no-llm
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request

from . import tools

SYSTEM_PROMPT = """You are a 5G network provisioning agent for an Open5GS + UERANSIM test network
running in Docker. You can only act through the provided tools.

Procedure - follow it in this order:
1. Turn the user's request into a network intent and call create_config.
   Defaults if the user does not say otherwise: mcc "001", mnc "01", tac 1, apn "internet",
   sst 1, sd 1. IMSIs are 15 digits and must start with MCC+MNC. If the user gives no IMSI,
   use 00101000000000N for UE N. Always pass mcc/mnc as strings (keep leading zeros).
   The core (AMF, SMF, UPF, NRF, AUSF, UDM, UDR, PCF, NSSF, BSF) is always deployed.
2. Call validate_config. If it reports errors, fix the intent and call create_config again.
   Never start containers with an invalid configuration.
3. start_core, then add_subscriber for every UE, then start_ran.
4. For every UE: get_ue_status, then test_connectivity.
5. If anything fails, use get_logs on the relevant component (ue1, gnb, amf, smf, upf),
   explain the most likely cause, and try one fix.
If the request is impossible or contradictory (e.g. an IMSI from a different PLMN than the
network), do not guess: explain the problem and stop.
Finish with a short report: which UEs are registered, their IPs, and the ping result."""


def _schema(name: str, description: str, properties: dict | None = None, required=None) -> dict:
    return {"type": "function", "function": {
        "name": name, "description": description,
        "parameters": {"type": "object", "properties": properties or {}, "required": required or []}}}


_UE = {"type": "object", "properties": {
    "imsi": {"type": "string", "description": "15 digits, no 'imsi-' prefix"},
    "apn": {"type": "string"}, "sst": {"type": "integer"}, "sd": {"type": "integer"},
    "key": {"type": "string"}, "opc": {"type": "string"}}, "required": ["imsi"]}

TOOL_SCHEMAS = [
    _schema("create_config", "Generate Open5GS/UERANSIM configs and a compose file from a network intent.",
            {"intent": {"type": "object", "properties": {
                "name": {"type": "string"}, "mcc": {"type": "string"}, "mnc": {"type": "string"},
                "tac": {"type": "integer"}, "ue_subnet": {"type": "string"},
                "ues": {"type": "array", "items": _UE}}, "required": ["ues"]}}, ["intent"]),
    _schema("validate_config", "Check PLMN/TAC/slice/subnet consistency of the generated configs."),
    _schema("start_core", "Start MongoDB and all Open5GS network functions."),
    _schema("add_subscriber", "Add UE number ue_index (1-based) as a subscriber in the database.",
            {"ue_index": {"type": "integer"}}, ["ue_index"]),
    _schema("start_ran", "Start the UERANSIM gNB and all UEs."),
    _schema("get_ue_status", "Registration / PDU session / IP of a UE container (ue1, ue2, ...).",
            {"ue": {"type": "string"}}, ["ue"]),
    _schema("test_connectivity", "Ping from a UE through its 5G tunnel.",
            {"ue": {"type": "string"}, "target": {"type": "string"}, "count": {"type": "integer"}}, ["ue"]),
    _schema("get_logs", "Last log lines of a container (amf, smf, upf, gnb, ue1, ...).",
            {"container": {"type": "string"}, "lines": {"type": "integer"}}, ["container"]),
    _schema("get_network_status", "State of all containers of the current network."),
    _schema("teardown", "Stop and remove the current network."),
]


def _chat(messages: list[dict]) -> dict:
    body = json.dumps({"model": os.environ.get("LLM_MODEL", "qwen2.5:7b"), "messages": messages,
                       "tools": TOOL_SCHEMAS, "temperature": 0}).encode()
    req = urllib.request.Request(
        os.environ.get("LLM_BASE_URL", "http://localhost:11434/v1").rstrip("/") + "/chat/completions",
        data=body, headers={"Content-Type": "application/json",
                            "Authorization": f"Bearer {os.environ.get('LLM_API_KEY', 'ollama')}"})
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.load(r)["choices"][0]["message"]


def call_tool(name: str, args: dict) -> dict:
    if name not in tools.TOOLS:
        return {"ok": False, "error": f"unknown tool {name}"}
    try:
        return tools.TOOLS[name](**args)
    except Exception as e:                       # errors go back to the LLM, not crash the run
        return {"ok": False, "error": f"{type(e).__name__}: {e}"}


def run_llm(request: str, max_steps: int = 40, verbose: bool = True) -> dict:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": request}]
    trace, t0 = [], time.time()
    for _ in range(max_steps):
        msg = _chat(messages)
        messages.append(msg)
        calls = msg.get("tool_calls") or []
        if not calls:
            return {"final": msg.get("content", ""), "trace": trace, "seconds": round(time.time() - t0, 1)}
        for c in calls:
            name = c["function"]["name"]
            args = json.loads(c["function"].get("arguments") or "{}")
            result = call_tool(name, args)
            trace.append({"tool": name, "args": args, "ok": result.get("ok")})
            if verbose:
                print(f"-> {name}({json.dumps(args)[:120]})  ok={result.get('ok')}", file=sys.stderr)
            messages.append({"role": "tool", "tool_call_id": c["id"], "content": json.dumps(result)[:6000]})
    return {"final": "stopped: step limit reached", "trace": trace, "seconds": round(time.time() - t0, 1)}


def run_scripted(intent: dict) -> dict:
    """Baseline without an LLM: same tools, fixed order. Use it to test the environment
    and as the comparison point for the evaluation."""
    t0 = time.time()
    steps = [("create_config", {"intent": intent}), ("validate_config", {})]
    out = []
    for name, args in steps:
        r = call_tool(name, args)
        out.append({"tool": name, **r})
        if not r.get("ok"):
            return {"ok": False, "steps": out}
    out.append({"tool": "start_core", **call_tool("start_core", {})})
    n = len(intent["ues"])
    for i in range(1, n + 1):
        out.append({"tool": "add_subscriber", **call_tool("add_subscriber", {"ue_index": i})})
    out.append({"tool": "start_ran", **call_tool("start_ran", {})})
    for i in range(1, n + 1):
        out.append({"tool": "get_ue_status", **call_tool("get_ue_status", {"ue": f"ue{i}"})})
        out.append({"tool": "test_connectivity", **call_tool("test_connectivity", {"ue": f"ue{i}"})})
    ok = all(s.get("ok") for s in out)
    return {"ok": ok, "steps": out, "seconds": round(time.time() - t0, 1)}


def main() -> None:
    ap = argparse.ArgumentParser(description="AI Network Provisioning agent (Group A-1)")
    ap.add_argument("request", nargs="?", help="natural-language request")
    ap.add_argument("--intent", help="JSON intent file (for --no-llm)")
    ap.add_argument("--no-llm", action="store_true", help="run the scripted baseline")
    a = ap.parse_args()
    if a.no_llm:
        if not a.intent:
            ap.error("--no-llm needs --intent FILE")
        with open(a.intent) as f:
            print(json.dumps(run_scripted(json.load(f)), indent=2))
    else:
        if not a.request:
            ap.error("give a request, e.g. \"Create a 5G network with two UEs\"")
        print(json.dumps(run_llm(a.request), indent=2))


if __name__ == "__main__":
    main()
