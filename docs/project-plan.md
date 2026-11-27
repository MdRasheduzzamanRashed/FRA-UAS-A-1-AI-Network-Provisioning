# Project Plan – Group A-1

Every member works on their own branch, commits from their own GitHub account and opens a
Pull Request (PR) into `main`. The lead reviews and merges. Each member presents their own
part (~4 min) at the final presentation on **8 March 2027**.

## Git workflow (for everyone)
```bash
git clone https://github.com/MdRasheduzzamanRashed/FRA-UAS-A-1-AI-Network-Provisioning.git
cd FRA-UAS-A-1-AI-Network-Provisioning
git checkout <your-branch>
git merge origin/main            # get the latest main before you start
# ... work ...
git add <files> && git commit -m "Short description of what you did"
git push origin <your-branch>
# then on GitHub: "Compare & pull request" -> base: main
```
Commit small and often (at least once per week) – the history is part of the grade.

## Milestones
| Date | Milestone | Rasheduzzaman | Zaria | Shakaut | Nowrin |
|---|---|---|---|---|---|
| 11 Jan | Foundation | Scripted baseline runs | Z1 | S1 | N1 |
| 18 Jan | M1 Architecture | Agent design | Z2 | S2 | N2 |
| 25 Jan | M2 Prototype | LLM agent on 3 requests | Z3 | S3 | N3 |
| 1 Feb | MCP integration | Agent uses MCP | – | S4 | – |
| 8–15 Feb | Experiments | Fix failures | Z4 | S5 | N4 |
| 22 Feb | M3 Tests | Model comparison | Z5 | – | N5 |
| 1 Mar | M4 Docs | Agent docs | Z6 | S6 | N6 |
| 8 Mar | Presentation | Agent + live demo | Network | MCP | Results |

---

## Zaria Fahamida – Network & Infrastructure (`Zaria-Fahamida`)

**Z1 – Run the basic network on your own VM (11 Jan)**
1. Ubuntu 26.04 VM, follow `README.md` (Docker, mongosh, images: `cd build-files && make all`).
2. Set `HOST_IP_ADDRESS` in `build-files/open5gs.env` to your VM IP.
3. `python3 -m src.provisioning.agent --no-llm --intent tests/intents/two_ues.json`
4. Write `docs/setup-x86.md`: every step + every error you hit and how you fixed it.
   Done when: both UEs show `registered: true` and ping has 0 % loss; screenshot in `results/screenshots/`.

**Z2 – Network figure (18 Jan)**: draw the 5G network used (UE1..N, gNB, AMF, SMF, UPF, NRF, AUSF, UDM, UDR, PCF, NSSF, MongoDB) with interfaces N1/N2/N3/N4/N6 and IPs from the compose file. Save as `docs/diagrams/a1-network.png` and add it to `docs/architecture.md`.

**Z3 – Bigger scenario (25 Jan)**: create `tests/intents/five_ues_two_slices.json` (5 UEs, slices SST1/SD1 and SST1/SD2) and run it. Record the result in `docs/implementation.md`.

**Z4 – Fault configurations (8 Feb)**: create 3 broken intents/configs in `tests/faults/` (wrong PLMN in UE, wrong TAC in gNB, subscriber missing). For each, write what goes wrong and which log line shows it.

**Z5 – Wireshark (22 Feb)**: capture on `br-ogs` during registration + PDU session (`sudo tcpdump -i br-ogs -w results/wireshark/registration.pcap`). Add 2 screenshots with NGAP/NAS messages explained in `docs/testing.md`.

**Z6 – Docs (1 Mar)**: "Network" section in `docs/implementation.md`.

---

## Md Shakaut Kader – MCP Server & Tests (`Md-Shakaut-Kader`)

**S1 – Environment + read the code (11 Jan)**: run the offline tests
(`python3 -m unittest discover -s tests -t .`) and the dry run
(`PROVISION_DRY_RUN=1 python3 -m src.provisioning.agent --no-llm --intent tests/intents/two_ues.json`).
Write a short summary of every tool in `src/provisioning/tools.py` into `docs/architecture.md` (table: tool, input, output).

**S2 – Architecture figure (18 Jan)**: figure User → LLM agent → MCP/tools → Docker/Open5GS. Save as `docs/diagrams/a1-architecture.png`.

**S3 – Unit tests (25 Jan)**: add `tests/test_tools.py` – for each tool one test in dry-run mode
(check the command that would run) + one test for an invalid input being refused.

**S4 – MCP server (1 Feb)**: `src/mcp_server/server.py` using the official MCP Python SDK
(`pip install mcp`, `FastMCP`). Expose every function in `tools.TOOLS` as an MCP tool. Test it with
MCP Inspector (`npx @modelcontextprotocol/inspector python3 -m src.mcp_server.server`); screenshot to `results/screenshots/`.

**S5 – Connect a client (8 Feb)**: show that an MCP client (Claude Desktop or MCP Inspector) can provision the 2-UE network through your server. Document the config in `docs/implementation.md`.

**S6 – Docs (1 Mar)**: "MCP server" section in `docs/implementation.md`.

---

## Nowrin Tasnin Sinthia – Evaluation & Testing (`Nowrin-Tasnin-Sinthia`)

**N1 – Environment (11 Jan)**: run the offline tests and the dry run (see S1). Read `tests/eval_requests.json` and `task.md` (use cases U1–U4).

**N2 – Measurement plan (18 Jan)**: in `docs/testing.md` define exactly how each metric is measured (U1–U4), the CSV columns and how many runs per request.

**N3 – Evaluation runner (25 Jan)**: `tests/run_eval.py` – reads `tests/eval_requests.json`, calls `run_llm()` from `src/provisioning/agent.py` for each request, calls `teardown` in between, writes one CSV row per run to `results/measurements/eval_<model>_<date>.csv` (id, run, expected, outcome, ues_ok, ping_loss, seconds, tool_calls).

**N4 – Run experiments (8–15 Feb)**: 3 runs × 10 requests for each model the lead selects.

**N5 – Charts (22 Feb)**: `results/measurements/plot.py` → success rate per model, time per request, tool calls per request (PNG). Comparison LLM vs scripted baseline.

**N6 – Docs (1 Mar)**: results section in `docs/testing.md` + slides for the results part.
