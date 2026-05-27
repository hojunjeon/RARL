# Multi-Agent Learning Harness

## Goal

Build a fresh RobotRL base that can be run and verified on Windows without
MuJoCo, Gymnasium, PyTorch, or other heavy dependencies. The first milestone is
not robotics realism. It is a clean training loop that proves the project can
coordinate multiple learning agents, write artifacts, and evaluate behavior
from reproducible metrics.

## Architecture

- `LineWorldEnv` owns the shared episode state.
- Each `QLearningAgent` owns one tabular policy.
- `train()` creates the environment, creates one learner per agent id, runs
  episodes, updates policies, and writes JSON artifacts.
- `robotrl.cli` exposes the first runnable training command.

## Outputs

- `metrics.json`: seed, episode count, agent count, success rates, timeout
  count, last-window steps and reward, and per-episode details.
- `policy.json`: environment configuration and each agent's Q table snapshot.

## Verification Contract

Run:

```powershell
python -m unittest discover -s tests
python -m robotrl.cli train --episodes 60 --seed 7
```

A useful run should create both JSON artifacts under the next numbered
`runs\learning\run_NNN_*` directory and show a high `success_rate_last_10`.
Completion should still be judged from the artifacts, not from success rate
alone.
