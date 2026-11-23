# Testing and Evaluation

## 1. Unit tests (offline)
`python -m unittest discover -s tests -t .` – config generation, PLMN/TAC/slice validation,
fault detection (injected TAC and PLMN mismatch), intent rejection, tool allow-list.

## 2. Integration test
Scripted baseline on the real network: `tests/intents/two_ues.json` →
2 UEs registered, PDU sessions up, ping 8.8.8.8 with 0 % loss.

## 3. Agent evaluation
Run every request in `tests/eval_requests.json` 3× per model; record in
`results/measurements/eval_<model>_<date>.csv`:

| id | run | expected | outcome | ues_ok | ping_loss | seconds | tool_calls | notes |
|----|-----|----------|---------|--------|-----------|---------|-----------|-------|

Metrics: success rate on valid requests (U1), correct rejection rate (U2), mean time (U3),
mean tool calls (U4), failure categories.

## Results
_to be filled (M3, 22 Feb 2027)_
