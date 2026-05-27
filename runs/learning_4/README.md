# RobotRL learning_4 - Single-object random generalization

## Goal

learning_4 resets the direction after the fixed-position multi-object lanes. The target is not a memorized routine for one known object coordinate. The target is a single-object policy that can reliably find, grasp, lift, carry, place into the collidable box, and return home when the object starts at randomized positions in the robot-front workspace.

Only after this single-object randomized skill is visually and numerically stable should the project move back to two random objects.

## Stage Plan

| Stage | Environment | Object start radius | Success gate |
| --- | --- | ---: | --- |
| 0 | `RobotRLFetchBoxPlaceBasicRandomNarrow-v0` | `0.02` | Basic in-box placement from a narrow random start range |
| 1 | `RobotRLFetchBoxPlaceBasicRandomMedium-v0` | `0.05` | Basic in-box placement from a wider start range |
| 2 | `RobotRLFetchBoxPlaceBasicRandomWide-v0` | `0.08` | Basic in-box placement from the wide robot-front range |
| 3 | `RobotRLFetchBoxPlaceRandomWide-v0` | `0.08` | Strict final in-box placement from the wide range |
| 4 | `RobotRLFetchBoxPlaceRandomWideReturnHome-v0` | `0.08` | Strict final in-box placement plus gripper/end-effector home return |
| 5 | Planned next lane | random 2 objects | Only after Stage 4 passes metrics and video review |

## Stage Advancement Rule

Do not advance on scalar metrics alone.

Each stage can advance only when both gates pass:

1. Numeric gate:
   - `success_rate >= 0.8` over the configured eval episodes.
   - The eval record has nonzero episodes and a rollout video/GIF artifact.
   - For return-home stages, diagnostics must show home return while final placement remains true.
2. Video gate:
   - Review the latest rollout GIF/video before accepting the stage.
   - The visible behavior must show a real approach, grasp or stable contact, lift/carry, over-wall or physically valid placement path, release/settle in the box, and home return when required.
   - Reject scalar success if the object or arm passes through the box, tray, shelf, or table, if the object slides/teleports into success, or if success is credited without a stable physical pick-and-place.

If the numeric gate is met but video has not been reviewed, r30o must classify the state as `아직 애매함` and hold the stage. It should report the exact video path that needs inspection instead of advancing or changing code.

## R30O Judgment

Every r30o run judges first and classifies exactly one state:

- `진전 있음`: metrics improve or the stage completes, and video evidence is physically valid.
- `아직 애매함`: training is running, metrics are inconclusive, or numeric success exists but video has not been checked.
- `명백히 아님`: metrics are flat in the wrong direction, diagnostics contradict the goal, or video shows penetration, teleport/slide success, fixed-position overfitting, or success without stable grasp/place.

For `진전 있음` or `아직 애매함`, r30o must not modify code. For `명백히 아님`, r30o uses executor/coding and verifier/evaluation subagents and only accepts a correction when verifier score is greater than 90.

## Active Run

### run_001_single_object_random_generalization_seed7

Command:

```powershell
python -m robotrl.cli fetch-loop --curriculum single-random-to-return --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_4\run_001_single_object_random_generalization_seed7
```

Notes:

- This run starts from scratch to avoid carrying fixed-coordinate behavior from earlier single-object and two-object lanes.
- The first useful signal is stable success in `RobotRLFetchBoxPlaceBasicRandomNarrow-v0` with rollout video showing a real physical pick-and-place from more than one sampled start position.
- The next learning direction after Stage 4 is two random objects, not fixed object slots.
