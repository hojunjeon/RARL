# RobotRL Learning 2 Run Index

`learning_2` is the sequential multi-object continuation lane. Runs 001 and 002
kept the run16 observation shape by exposing only the current active object.
Run 003 started a new policy with an explicit one-hot active-object cue appended
to the observation, so object1 gets an unambiguous training signal after object0
is placed. Run 004 keeps that 27-value observation and adds a wider basic
two-object placement stage before strict cued placement.

| Run | Status |
| --- | --- |
| `run_001_multi_object_2_sequential_return_seed7` | Invalid direction after 8 eval iterations: `success_rate=0.0`, `object1_in_box_rate=0.0`, and `all_objects_in_box_rate=0.0`; PID `76956` stopped; artifacts are retained |
| `run_002_multi_object_2_curriculum_seed7` | Invalid direction after 10 eval iterations: stage 1 still had `success_rate=0.0`, `object1_in_box_rate=0.0`, and `all_objects_in_box_rate=0.0` while `object0_in_box_rate` reached 0.9; PID `65900` stopped; artifacts are retained |
| `run_003_multi_object_2_active_cue_seed7` | Invalid direction after 6 eval iterations: `success_rate=0.0`, `object0_in_box_rate=0.0`, `object1_in_box_rate=0.0`, and `all_objects_in_box_rate=0.0`; PID `45148` was still live at R30O correction time; artifacts are retained |
| `run_004_multi_object_2_basic_active_cue_seed7` | Restart target: three-stage curriculum with `RobotRLFetchBoxPlaceTwoSequentialBasicCued-v0` stage 1, `RobotRLFetchBoxPlaceTwoSequentialCued-v0` stage 2, and `RobotRLFetchBoxPlaceTwoSequentialReturnHomeCued-v0` stage 3; starts from scratch and preserves the 27-value active-cue observation |

## R30O Command

```powershell
python -m robotrl.cli fetch-loop --curriculum two-to-two-return --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_2\run_004_multi_object_2_basic_active_cue_seed7
```

Do not resume run16 or run002 checkpoints into run003. Those checkpoints were
trained against the legacy 25-value observation shape and remain compatible only
with the non-cued env IDs.

## R30O Judgment Contract

Every 30-minute check should inspect live Python processes, this run directory,
`fetch_loop_spec.json`, `eval_results.json`, checkpoints, TensorBoard event
files, and rollout GIF/video artifacts. Classify exactly one of:

- `clearly_wrong`
- `still_ambiguous`
- `progress`

Keep the current direction for `still_ambiguous` or `progress`. If the state is
`clearly_wrong`, correct the smallest reversible code/config issue and restart a
new numbered `learning_2` run. Scalar success is invalid if video/diagnostics
show tray, box, or shelf penetration, or if either object leaves the box before
return-home success.

Automation id: `robotrl-r30o-learning-2`.
