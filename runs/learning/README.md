# RobotRL Learning Run Index

Retained learning runs are numbered by execution order. Smoke, demo, probe, and
short validation folders were removed from `runs` to keep this directory focused
on actual learning attempts.

| Run | Previous folder | Status |
| --- | --- | --- |
| `run_001_fetch_pick_place_loop_seed7` | `fetch_pick_place_loop_seed7` | FetchPickAndPlace loop, retained for history |
| `run_002_fetch_box_place_loop_seed7` | `fetch_box_place_loop_seed7` | Box placement baseline loop |
| `run_003_fetch_box_place_dense_loop_seed7` | `fetch_box_place_dense_loop_seed7` | Dense reward loop |
| `run_004_fetch_box_visible_dense_loop_seed7` | `fetch_box_visible_dense_loop_seed7` | Visible dense reward loop |
| `run_005_fetch_box_visible_curriculum_loop_seed7` | `fetch_box_visible_curriculum_loop_seed7` | Curriculum loop, evaluation JSON missing |
| `run_006_fetch_box_right_curriculum_loop_seed7` | `fetch_box_right_curriculum_loop_seed7` | Right-side curriculum loop |
| `run_007_fetch_box_right_shaped_loop_seed7` | `fetch_box_right_shaped_loop_seed7` | Right-side shaped loop |
| `run_008_fetch_box_right_controlled_loop_seed7` | `fetch_box_right_controlled_loop_seed7` | Right-side controlled loop |
| `run_009_fetch_box_right_balanced_loop_seed7` | `fetch_box_right_balanced_loop_seed7` | Right-side balanced loop |
| `run_010_improvement_loop` | new | Multi-agent improvement loop harness start, low target proof |
| `run_011_improvement_loop_default_check` | new | Default improve-loop proof reaching target score |
| `run_012_fetch_box_right_curriculum_dummyvec_seed7` | new | Invalidated after video review: scalar success came from non-colliding tray geoms, fixed before next restart |
| `run_013_fetch_box_right_curriculum_collidable_seed7` | new | Rejected R30O evidence: collidable tray exposed that the strict right-curriculum target was too hard for first-stage behavior |
| `run_014_fetch_box_basic_to_final_curriculum_seed7` | new | Completed: encoded basic-to-final curriculum reached final-stage success, `success_model.zip` and `stage_02_iteration_012_rollout.gif` generated |
| `run_015_fetch_box_final_to_return_home_seed7` | new | Active but clearly wrong: stage 02 kept final placement near the box while return-home success stayed at 0.0 |
| `run_016_fetch_box_return_home_signal_seed7` | new | Completed: return-home signal correction reached place-plus-return success, `success_model.zip` and `stage_01_iteration_008_rollout.gif` generated |
