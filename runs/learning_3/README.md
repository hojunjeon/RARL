# RobotRL learning_3 run index

`learning_3` starts from the completed `learning_2` two-object sequential
policy, but rejects scalar success when an object is credited after passing
through a tray wall. The lane requires each object to have a valid over-wall
entry before it can count as placed.

| Run | Status |
| --- | --- |
| `run_001_multi_object_2_over_wall_return_seed7` | Invalid: after 12 eval iterations object0 learned valid over-wall entry, but object1 stayed at `object1_in_box_rate=0.0` and `object1_valid_box_entry_rate=0.0`; the shared tight target left no learnable second-object slot after object0 placement |
| `run_002_multi_object_2_over_wall_return_slots_seed7` | Invalid: after 9 eval iterations object0 reached `object0_in_box_rate=1.0` and `object0_valid_box_entry_rate=1.0` from iteration 2 onward, but object1 stayed at `object1_in_box_rate=0.0` and `object1_valid_box_entry_rate=0.0`; classified as `clearly_wrong` |
| `run_003_multi_object_2_over_wall_basic_slots_seed7` | Invalid: after 9 eval iterations object0 mostly reached `object0_in_box_rate=1.0` and `object0_valid_box_entry_rate=1.0`, but object1 stayed at `object1_in_box_rate=0.0` and `object1_valid_box_entry_rate=0.0`; the stage still required object0 and object1 together before object1 got a clean active-start curriculum |
| `run_004_multi_object_2_over_wall_object_stages_seed7` | Invalid: object0-only stage succeeded immediately, but Object1Basic stayed stuck through iterations 2-9 with `object1_in_box_rate=0.0`, `object1_valid_box_entry_rate=0.0`, and only `0.00-0.02m` object1 lift; stopped PID `27392` |
| `run_005_multi_object_2_object1_lift_seed7` | Invalid: run005 was stopped at PID `58336`; Stage 0 Object0Basic succeeded, but Stage 1 Object1Basic stayed stuck through iterations 2-10 with `object1_in_box_rate=0.0`, `object1_valid_box_entry_rate=0.0`, and mean max object1 lift only `0.0-0.0277m`, so the lift reward alone did not create a learnable over-wall motion |
| `run_006_multi_object_2_object1_lift_stage_seed7` | Active: verifier accepted the correction at `94/100`; started as PID `75296`; inserts an Object1 lift-before-wall substage between Object0Basic and Object1Basic; the lift substage can advance on active-object lift without granting box credit, while Object1Basic/final stages still require `object1_valid_box_entry` before `object1_in_box` or scalar placement success can count |

## Previous run 003 command

```powershell
python -m robotrl.cli fetch-loop --curriculum two-over-wall-return --resume-from runs\learning_2\run_004_multi_object_2_basic_active_cue_seed7\success_model.zip --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_3\run_003_multi_object_2_over_wall_basic_slots_seed7
```

## Previous run 004 command

```powershell
python -m robotrl.cli fetch-loop --curriculum two-over-wall-return --resume-from runs\learning_2\run_004_multi_object_2_basic_active_cue_seed7\success_model.zip --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_3\run_004_multi_object_2_over_wall_object_stages_seed7
```

## Previous run 005 command

```powershell
python -m robotrl.cli fetch-loop --curriculum two-over-wall-return --resume-from runs\learning_2\run_004_multi_object_2_basic_active_cue_seed7\success_model.zip --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_3\run_005_multi_object_2_object1_lift_seed7
```

## Active run 006 command

```powershell
python -m robotrl.cli fetch-loop --curriculum two-over-wall-return --resume-from runs\learning_2\run_004_multi_object_2_basic_active_cue_seed7\success_model.zip --chunk-timesteps 50000 --n-envs 6 --learning-starts 10000 --checkpoint-interval 50000 --eval-episodes 20 --success-threshold 0.8 --seed 7 --output-dir runs\learning_3\run_006_multi_object_2_object1_lift_stage_seed7
```

## R30O judgment contract

- Scalar success is invalid unless `object0_valid_box_entry_rate`,
  `object1_valid_box_entry_rate`, `all_objects_in_box_rate`, and
  `multi_place_return_success_rate` all support the same threshold, except for
  the explicit Object1 lift-before-wall substage where
  `success_requires_valid_box_entry_rate=0.0` and success means lift only.
- `object1_in_box=1` with `object1_valid_box_entry=0` is an automatic
  `clearly_wrong` judgment.
- `run_006` should first clear the object0-only stage, then show lift-stage
  `mean_max_object_lift >= 0.075` progress before advancing to Object1Basic.
  Object1Basic must then show `object1_valid_box_entry_rate > 0.0`; object1
  remaining at 0.0 across repeated Object1Basic evals is still `clearly_wrong`.
- Rollout video must show both objects entering over the collidable tray wall,
  not through it.
