# Implementation

## Code layout
| File | Purpose |
|------|---------|
| `src/provisioning/intent.py` | `NetworkIntent` / `UE` data model and input validation (IMSI format, PLMN prefix, ranges) |
| `src/provisioning/configgen.py` | Generates `configs/generated/<name>/` and `compose-files/generated/<name>/docker-compose.yaml`; cross-file validation |
| `src/provisioning/tools.py` | The agent's tools (Docker, dbctl, logs, ping) with allow-lists and dry-run mode |
| `src/provisioning/agent.py` | LLM tool-calling loop, system prompt, tool schemas, scripted baseline, CLI |
| `tests/test_configgen.py` | Offline unit tests (no Docker needed) |

## Running
```bash
pip install -r requirements.txt

# Offline tests
python -m unittest discover -s tests -t .

# Scripted baseline (needs Docker + images, see README)
python -m src.provisioning.agent --no-llm --intent tests/intents/two_ues.json

# LLM agent (example with local Ollama)
ollama pull qwen2.5:7b
export LLM_BASE_URL=http://localhost:11434/v1 LLM_MODEL=qwen2.5:7b
python -m src.provisioning.agent "Create a 5G network with two UEs and test the connection"

# Dry run without Docker: print the commands instead of executing them
PROVISION_DRY_RUN=1 python -m src.provisioning.agent --no-llm --intent tests/intents/two_ues.json
```

## Notes
- MCC/MNC are always written as strings so leading zeros survive (`"01"` ≠ `"001"`).
- `add_subscriber` removes the IMSI first, so repeated runs do not hit `E11000 duplicate key`.
- SD is stored in MongoDB as 6 hex digits (`000001`).
- ARM64 hosts: build images locally first (`cd build-files && make all`).

## Problems and solutions
| Problem | Solution |
|---------|----------|
| _to be filled during the project_ | |
