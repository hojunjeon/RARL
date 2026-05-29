# RobotRL 30-Minute Orchestrator Protocol

Reusable name: **R30O Protocol**

Use this name when referring to the training workflow where Codex acts as the
orchestrator, checks RobotRL progress every 30 minutes, and only triggers
correction work when intermediate evidence proves the current learning direction
is wrong.

## Purpose

The R30O Protocol prevents long blind training runs. The orchestrator does not
wait for a full run to finish if the checkpoint, logs, metrics, or rollout
already show that the current direction is failing.

## Reward-Design Reference

For RobotRL pick-and-place training, R30O must use
`docs/r30o_pick_place_reward_design_db.md` as the reward-design reference before
changing rewards, gates, diagnostics, curricula, or visual approval criteria.
The DB is the local source for:

- the physical success contract;
- reward-stage priorities;
- anti-push, anti-slide, and anti-penetration penalties;
- telemetry needed to approve or reject a stage;
- external MuJoCo, FetchPickAndPlace, SAC, and HER references.

Do not design a reward from scalar goal distance alone. The current target is
stable randomized pick-and-place: approach, grasp, lift, carry, physically valid
box entry, release, settle, and no wall/table tunneling.

## Learning Roadmap

Call the staged path toward `n` objects in the box the **Learning Roadmap**.
R30O must keep the active roadmap stage explicit in reports and handoff notes.

| Roadmap stage | Name | Completion target |
| ---: | --- | --- |
| 1 | Single-object randomized pick-and-place | One randomly spawned object is grasped, lifted, carried, placed in the box, released, settled, and visually approved. |
| 2 | Two-object cued placement | Two objects are placed in the box with active-object cues and without fixed-position overfitting. |
| 3 | Two-object randomized placement | Two randomly spawned objects are placed in the box with stable grasp/lift/carry/place behavior for each object. |
| 4 | Incremental `n`-object placement | Increase object count only after the previous count passes numeric, telemetry, and visual gates. |
| 5 | Final `n`-object generalization | The requested `n` objects are placed in the box across held-out seeds without pushing, sliding, tunneling, or scalar-only success. |

The current active roadmap stage is **Stage 1**. When Stage 1 clears, R30O
continues to Stage 2. Repeat this pattern until the last roadmap stage clears.

## Roles

- **Orchestrator**: judges progress, decides whether to continue or trigger
  correction, starts the next training run after an accepted correction.
- **Coding subagent**: makes the smallest reversible code or configuration
  change for a clear failure mode.
- **Evaluation subagent**: scores the changed result against the RobotRL
  manipulation-training criteria.

The orchestrator should judge first and avoid coding directly. Coding work starts
only after the state is classified as clearly wrong.

## 30-Minute Check

Every check inspects:

- live Python processes for `robotrl`, `fetch-loop`, `fetch-train`, or
  Stable-Baselines3 training;
- the latest `runs/learning/run_*` directory;
- `fetch_loop_spec.json` or `fetch_training_spec.json`;
- `logs/`;
- `eval_results.json`;
- checkpoints;
- rollout GIF or video artifacts.

TensorBoard alone is not a liveness signal. A retained TensorBoard process can
exist even when training has stopped.

## Three-Way Judgment

Classify each check into exactly one state.

### 1. Clearly Wrong

Use this when intermediate evidence proves the direction should not continue.

Examples:

- training process crashed or repeatedly exits before useful checkpoints;
- no new checkpoints, evaluations, or rollout artifacts appear;
- after a meaningful new chunk, `mean_max_object_lift` stays at `0.0`;
- gripper-object distance does not improve;
- rollout repeatedly shows the same non-contact or non-grasp behavior;
- logs show a reproducible pipeline failure such as vectorized environment
  subprocess failure.

Action: start the correction loop.

### 2. Still Ambiguous

Use this when success is not present yet, but the evidence is not enough to
reject the direction.

Examples:

- success rate is still `0.0`, but distance to object or goal is improving;
- gripper gets closer to the object;
- first contact appears but grasp/lift is not stable yet;
- rollout quality changes without satisfying the full task.

Action: do not modify code. Continue to the next checkpoint or next 30-minute
check.

### 3. Progress

Use this when the current direction is working and should continue.

Examples:

- object lift appears and grows;
- object-goal distance decreases;
- grasp and carry behavior become visible;
- evaluation success rate rises with matching rollout evidence.

Action: continue training and raise the next behavioral gate.

## Correction Loop

Only run this loop for **Clearly Wrong**.

1. Spawn a coding subagent with the observed failure mode and a narrow write
   scope.
2. The coding subagent makes the smallest reversible fix.
3. Spawn or reuse an evaluation subagent to score the changed result.
4. If the evaluation score is `<= 90`, repeat coding and evaluation with the new
   evidence.
5. When the evaluation score is `> 90`, the orchestrator restarts training with
   the accepted configuration.

If a concrete blocker is proven, stop the loop and report the blocker instead of
pretending the score passed.

## Evaluation Score

The evaluation subagent scores from 0 to 100. A passing correction requires a
score greater than 90.

The score should consider:

- training process stability;
- whether artifacts are written under `runs/learning`;
- checkpoint and evaluation continuity;
- rollout evidence;
- behavior quality, not success rate alone;
- whether the correction matches the observed failure mode;
- whether the change is small and reversible.

## Behavioral Gates

Do not treat `success_rate` as the only completion signal. The manipulation task
must progress through these gates:

1. approach the object;
2. grasp the object;
3. lift the object;
4. carry toward the target box;
5. lower near the target floor;
6. open/release;
7. object settles in the target area;
8. gripper moves away.

When one gate starts working, the next correction target should move to the next
gate rather than repeatedly tuning the earlier one.

## Restart Contract

After a passing correction, restart training with an explicit command and a new
or clearly preserved output directory under `runs/learning`.

The report must include:

- judgment state;
- evidence used;
- changed files, if any;
- evaluation score;
- restart command;
- output directory;
- remaining risk.
