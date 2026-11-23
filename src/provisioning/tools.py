"""The agent's tools. Every network action goes through this file.

Security rule (Handbook topic 14/21): the agent never gets a shell. Each tool runs a
fixed command with validated arguments, and only on containers this project created.

Set PROVISION_DRY_RUN=1 to record commands instead of executing them (useful on a
machine without Docker, and for unit tests).
"""
from __future__ import annotations

import os
import re
import subprocess
import time
from pathlib import Path

from . import configgen
from .intent import NetworkIntent

REPO = configgen.REPO
ENV_FILE = REPO / "build-files" / "open5gs.env"
DBCTL = REPO / "open5gs-dbctl"
DB_URI = os.environ.get("OPEN5GS_DB_URI", "mongodb://localhost/open5gs")
CORE_SERVICES = ["db", *configgen.CORE_NFS, "webui"]

DRY_RUN = os.environ.get("PROVISION_DRY_RUN") == "1"
COMMAND_LOG: list[list[str]] = []      # every command executed (or simulated)

# The network the agent is currently working on (set by create_config)
_state: dict = {"intent": None, "compose": None}


# --------------------------------------------------------------------------
# helpers
# --------------------------------------------------------------------------
def _run(cmd: list[str], timeout: int = 180) -> dict:
    COMMAND_LOG.append(cmd)
    if DRY_RUN:
        return {"ok": True, "dry_run": True, "cmd": " ".join(cmd), "output": ""}
    try:
        p = subprocess.run(cmd, cwd=REPO, capture_output=True, text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"ok": False, "cmd": " ".join(cmd), "output": f"timeout after {timeout}s"}
    out = (p.stdout + p.stderr)[-4000:]          # keep LLM context small
    return {"ok": p.returncode == 0, "cmd": " ".join(cmd), "output": out}


def _compose(*args: str) -> list[str]:
    if not _state["compose"]:
        raise RuntimeError("no network created yet - call create_config first")
    return ["docker", "compose", "--env-file", str(ENV_FILE), "-f", _state["compose"], *args]


def _known_containers() -> set[str]:
    intent: NetworkIntent | None = _state["intent"]
    n = len(intent.ues) if intent else 0
    return {*CORE_SERVICES, "gnb", *(f"ue{i}" for i in range(1, n + 1))}


def _check_container(name: str) -> None:
    if name not in _known_containers():
        raise ValueError(f"unknown container '{name}'. Allowed: {sorted(_known_containers())}")


# --------------------------------------------------------------------------
# tools (each returns a JSON-serialisable dict)
# --------------------------------------------------------------------------
def create_config(intent: dict) -> dict:
    """1+2. Understand requirements -> generate configuration."""
    ni = NetworkIntent.from_dict(intent)
    result = configgen.create_config(ni)
    _state["intent"] = ni
    _state["compose"] = str(REPO / result["compose_file"])
    return {"ok": True, **result}


def validate_config() -> dict:
    """3. Validate the generated configuration before starting anything."""
    if not _state["intent"]:
        return {"ok": False, "errors": ["no network created yet"]}
    return configgen.validate_config(_state["intent"].name)


def start_core() -> dict:
    """4. Start MongoDB and the Open5GS network functions."""
    return _run(_compose("up", "-d", *CORE_SERVICES))


def add_subscriber(ue_index: int) -> dict:
    """Register UE number ue_index (1-based) in the Open5GS database (idempotent)."""
    ni: NetworkIntent = _state["intent"]
    if not ni or not (1 <= ue_index <= len(ni.ues)):
        return {"ok": False, "output": f"ue_index must be 1..{len(ni.ues) if ni else 0}"}
    ue = ni.ues[ue_index - 1]
    _run([str(DBCTL), f"--db_uri={DB_URI}", "remove", ue.imsi])   # avoid E11000 duplicate key
    return _run([str(DBCTL), f"--db_uri={DB_URI}", "add_ue_with_slice",
                 ue.imsi, ue.key, ue.opc, ue.apn, str(ue.sst), f"{ue.sd:06x}"])


def start_ran() -> dict:
    """5+6. Start the UERANSIM gNB and all UEs (UEs register automatically)."""
    ues = [f"ue{i}" for i in range(1, len(_state["intent"].ues) + 1)]
    return _run(_compose("up", "-d", "gnb", *ues))


def get_ue_status(ue: str, wait_s: int = 20) -> dict:
    """Read the UE log and report registration / PDU session / IP address."""
    _check_container(ue)
    deadline = time.time() + (0 if DRY_RUN else wait_s)
    while True:
        logs = _run(["docker", "logs", "--tail", "200", ue])["output"]
        status = {
            "ue": ue,
            "registered": "Initial Registration is successful" in logs,
            "pdu_session": "PDU Session establishment is successful" in logs,
            "ip": (m.group(1) if (m := re.search(r"TUN interface\[\w+, ([\d.]+)\] is up", logs)) else None),
            "errors": [l for l in logs.splitlines() if "[error]" in l.lower()][-5:],
        }
        if (status["pdu_session"] and status["ip"]) or time.time() > deadline or DRY_RUN:
            status["ok"] = status["registered"] and status["pdu_session"]
            return status
        time.sleep(2)


def test_connectivity(ue: str, target: str = "8.8.8.8", count: int = 4) -> dict:
    """7. Ping through the UE's tunnel (UE -> gNB -> GTP-U -> UPF -> Internet)."""
    _check_container(ue)
    if not re.fullmatch(r"[\w.-]{1,253}", target) or not (1 <= count <= 20):
        return {"ok": False, "output": "invalid target or count"}
    r = _run(["docker", "exec", ue, "ping", "-I", "uesimtun0", "-c", str(count), target], timeout=60)
    m = re.search(r"(\d+)% packet loss", r["output"])
    rtt = re.search(r"= [\d.]+/([\d.]+)/", r["output"])
    r["packet_loss_pct"] = int(m.group(1)) if m else None
    r["avg_rtt_ms"] = float(rtt.group(1)) if rtt else None
    r["ok"] = r["ok"] and r["packet_loss_pct"] == 0 if not DRY_RUN else True
    return r


def get_logs(container: str, lines: int = 50) -> dict:
    """8. Detect errors: read the last lines of a container's log."""
    _check_container(container)
    return _run(["docker", "logs", "--tail", str(max(1, min(lines, 300))), container])


def get_network_status() -> dict:
    """List the project's containers and their state."""
    return _run(_compose("ps", "--format", "table {{.Name}}\t{{.State}}\t{{.Status}}"))


def teardown() -> dict:
    """Stop and remove all containers of the current network."""
    return _run(_compose("down"))


TOOLS = {f.__name__: f for f in (create_config, validate_config, start_core, add_subscriber,
                                  start_ran, get_ue_status, test_connectivity, get_logs,
                                  get_network_status, teardown)}
