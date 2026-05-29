# R30O Pick-And-Place Reward Design DB

Purpose: reference database for the next R30O training run. The target behavior is: spawn an object randomly inside the robot-front workspace, grasp it stably, lift it clear of the support surface, carry it without pushing/sliding/tunneling, place it inside the left-side tray, release it, and leave it settled.

## Local RobotRL Facts

- Tray center: `RIGHT_BOX_CENTER_XY = (1.42, 0.92)` in `robotrl/fetch_envs.py`. Despite the legacy constant name, this is now the robot-left tray target.
- Single-object curriculum start center: `CURRICULUM_OBJECT_START_XY = (1.30, 0.75)`.
- Two-object start centers: `TWO_OBJECT_START_XYS = ((1.27, 0.75), (1.35, 0.75))`.
- These starts keep objects in the robot-front workspace. Randomness comes from each curriculum stage's `object_start_radius`, so the robot cannot solve the task with a single fixed motion.
- Single-object randomized curricula apply `object_start_radius` around `CURRICULUM_OBJECT_START_XY`.
- Two-object over-wall curricula apply per-object jitter around `TWO_OBJECT_START_XYS`.
- Tray assets now use thicker and taller physical walls with explicit collision contact settings in:
  - `robotrl/assets/fetch_box_place.xml`
  - `robotrl/assets/fetch_box_place_two.xml`
- Current tray wall contact settings are intended to reduce wall tunneling: `condim=4`, friction `1.2 0.05 0.01`, stiff `solref`, high `solimp`, and `margin=0.003`.

## Current Reward Surface

Current shaped reward implementation: `RobotRLFetchBoxPlaceEnv._compute_shaped_reward`.

- Placement shaping:
  - `place_reward = -2.4*object_goal_distance - 1.4*object_goal_xy_distance - 0.5*object_height_error`
- Reach shaping:
  - `reach_reward = -0.35*gripper_object_distance`
- Grasp proximity:
  - `grasp_bonus = +0.2` when `gripper_object_distance < 0.055`
- Lift shaping:
  - `lift_bonus = 0.6 * min(object_lift / 0.08, 1.0)`
  - `carry_height_bonus = +0.35` when `0.035 <= object_lift <= 0.11`
  - `under_lift_penalty` when the gripper is near the object, the object is low, and the object is not near the goal.
  - `over_lift_penalty = -4.0 * max(0, object_lift - 0.12)`
- Near-tray lowering:
  - `lower_near_tray_bonus = 0.4 * (1 - object_height_error / 0.08)`, reduced when far in XY.
- Success bonus:
  - `tray_bonus = +4.0*is_success`
  - multi-object modes add in-box count, all-in-box, valid-entry, active-lift, or return-home terms depending on mode.

Problem: the current reward can still over-credit proximity and final distance if the object moves by pushing, wall contact, sliding, or penetration. R30O should use explicit behavior gates and diagnostics so visible grasping is required, not incidental object displacement.

## External References

### MuJoCo Contact And Penetration

- MuJoCo contact distance is positive when geoms are separated, zero at contact, and negative when penetrating.
- Contact dimensionality matters:
  - `condim=3`: normal plus tangential friction.
  - `condim=4`: adds torsional friction, useful for soft-finger grasp stability.
  - `condim=6`: adds rolling friction.
- Friction parameters represent sliding, torsional, and rolling components.
- `solref`, `solimp`, `margin`, and collision filtering affect how contacts resist penetration and slip.
- Sources:
  - https://mujoco.readthedocs.io/en/latest/computation/
  - https://mujoco.readthedocs.io/en/latest/XMLreference.html
  - https://mujoco.readthedocs.io/en/stable/modeling.html

### Fetch Pick-And-Place Baseline

- Gymnasium-Robotics FetchPickAndPlace uses a multi-goal setup with dict observations containing observation, achieved goal, and desired goal.
- Sparse success is block-target distance below `0.05 m`; dense reward is negative distance.
- Object starts and targets are randomized around the workspace.
- This baseline is useful as a sparse goal layer, but it is not strict enough for RobotRL's physical behavior requirement.
- Source:
  - https://robotics.farama.org/envs/fetch/pick_and_place/

### SAC And HER

- SAC is a common off-policy continuous-control baseline for this task type.
- In Stable-Baselines3, HER is a replay buffer (`HerReplayBuffer`), not a standalone algorithm.
- HER expects GoalEnv-style dict observations and a vectorized `compute_reward()`.
- If shaped reward depends on hidden trajectory state not represented in goals/infos, HER relabeling can become inconsistent.
- Use HER for sparse goal learning only when rewards can be recomputed correctly after goal relabeling.
- Sources:
  - https://stable-baselines3.readthedocs.io/en/master/modules/sac.html
  - https://stable-baselines3.readthedocs.io/en/master/modules/her.html
  - https://stable-baselines3.readthedocs.io/en/master/guide/examples.html#hindsight-experience-replay-her
  - https://papers.neurips.cc/paper/7090-hindsight-experience-replay
  - https://arxiv.org/abs/1707.01495

### Evaluation

- Use separate deterministic evaluation environments.
- Evaluate over multiple episodes, deterministic actions, and saved rollout videos.
- For RobotRL, scalar success must be gated by contact telemetry and visual review.
- Sources:
  - https://stable-baselines3.readthedocs.io/en/master/guide/rl_tips.html
  - https://stable-baselines3.readthedocs.io/en/master/guide/callbacks.html
  - https://stable-baselines3.readthedocs.io/en/master/common/evaluation.html
  - https://stable-baselines3.readthedocs.io/en/master/guide/examples.html#record-a-video

## R30O Success Contract

An episode is successful only if all of these are true:

1. The gripper reaches the randomized object without first sweeping it across the table.
2. The gripper establishes stable object contact or a stable grasp.
3. The object is lifted above the support surface before large XY transport.
4. The object remains near the gripper while airborne during transport.
5. The object enters the tray through physically valid motion, not through a wall.
6. The object is released inside the tray.
7. The object settles in the tray with low velocity and without gripper contact.
8. No major sliding, pushing, teleporting, wall penetration, or tray tunneling occurs.

Scalar goal distance alone is not a success signal for R30O.

## Proposed Reward Redesign

Keep final success sparse and physical, then shape only the path to that contract.

### Stage 1: Approach

- Reward decreasing gripper-object distance.
- Penalize object displacement before close gripper contact.
- Penalize high gripper velocity near the object.
- Prefer the gripper above/around the object, not below the object.

### Stage 2: Grasp Contact

- Reward both-finger or stable gripper-object contact when available.
- Reward low relative velocity between gripper and object.
- Reward the object staying close to the gripper for consecutive steps.
- Penalize one-frame taps that move the object without sustained contact.

### Stage 3: Lift

- Reward object height above its spawn/support height.
- Require lift before major XY progress toward the tray.
- Penalize object support contact while claiming lift.
- Penalize lifting too high above the useful carry band.

### Stage 4: Carry

- Reward XY progress toward an above-tray staging zone only while the object is airborne and close to the gripper.
- Penalize large object displacement when gripper-object contact is absent.
- Penalize tray-wall or table contact during transport.
- Penalize high object velocity near the tray.

### Stage 5: Place

- Reward descending toward the tray center from above the open tray area.
- Reward low object velocity inside the tray.
- Require valid over-wall/through-opening entry when the over-wall gate is enabled.
- Penalize wall contact with negative penetration depth.

### Stage 6: Release And Settle

- Reward gripper opening/separating only after the object is inside the tray.
- Reward object settled velocity below a threshold for consecutive steps.
- Penalize continued gripper-object contact after release.
- Apply return-home reward only after valid object placement is latched.

### Applied Correction: Run006 Release/Withdraw Reward

Run005 showed a repeatable exploit: scalar success reached `0.95`, but the rollout ended with the gripper still inserted inside the tray. For run006, the shaped reward now applies after placement:

- `release_bonus`: rewards gripper-object separation, gripper opening, and movement back toward the initial home pose.
- `post_place_contact_penalty`: penalizes continued close gripper-object contact after the object is already placed.

This does not replace the visual gate. R30O must still reject any rollout that lacks visible release, settle, and withdrawal from the tray.

### Applied Correction: Run007 Release Success Gate

Run006 showed that reward shaping alone was insufficient: high scalar-success rollouts still ended with the gripper inserted in the tray. For run007, the single-random curriculum's scalar success is hardened:

- Basic random stages require normal placement plus gripper opening, gripper-object separation, and gripper withdrawal from the tray area.
- Full random wide placement also requires the same release/withdraw gate before scalar success is counted.
- The final return-home stage keeps its stricter return-home success gate.

This makes scalar success a necessary but still not sufficient signal: visual approval remains mandatory before Learning Roadmap Stage 1 can advance.

### Applied Correction: Run008 Strict Withdraw Gate

Run007 proved the hard release gate helped the narrow random stage, but internal stage 02 still exposed a loose withdrawal definition. At 500k timesteps, iteration 10 reported `success_rate=0.95` while `video_place_return_success=0.0` and `place_return_success_rate=0.15`; visual review did not prove sufficient gripper withdrawal from the tray.

For run008, the release success gate uses `release_withdraw_distance=0.14m` instead of the tray half-size threshold. Scalar success must now require:

- object placed inside the robot-left tray;
- gripper open after placement;
- gripper separated from the object;
- gripper withdrawn well outside the tray area.

This correction keeps the same DB rule: do not approve a stage until telemetry and video jointly prove release, settle, and withdrawal, not just object-in-box distance.

## Penalty Terms To Add Or Strengthen

- `pregrasp_object_motion_penalty`: object moves materially before close gripper contact.
- `no_contact_displacement_penalty`: large object step displacement without gripper contact.
- `support_sliding_penalty`: object XY motion while object height remains near support height.
- `wall_penetration_penalty`: any sustained negative contact distance against tray walls.
- `wall_push_penalty`: high force or repeated wall contact while object is outside/at edge of tray.
- `invalid_inside_penalty`: object becomes inside the tray without prior airborne/grasp latch.
- `bounce_penalty`: high object velocity after tray entry.
- `late_gripper_contact_penalty`: gripper keeps pushing the object after it is inside the tray.

## Telemetry Required Before R30O Acceptance

Add or verify these diagnostics in eval records:

- `min_gripper_object_distance`
- `gripper_object_contact_steps`
- `stable_contact_steps`
- `object_lift`
- `max_object_lift`
- `airborne_steps`
- `airborne_transport_steps`
- `object_support_contact_steps`
- `tray_wall_contact_steps`
- `min_tray_wall_contact_distance`
- `max_step_object_displacement`
- `max_step_object_displacement_without_contact`
- `pregrasp_object_displacement`
- `valid_grasp_latched`
- `valid_lift_latched`
- `valid_carry_latched`
- `valid_physical_entry_latched`
- `release_after_entry_latched`
- `settled_in_box_steps`

Use these diagnostics as hard gates for visual-gated curricula. They should explain why a video is accepted or rejected.

## R30O Training Recommendation

1. Start R30O with the left-side tray and robot-front randomized object starts above.
2. Keep tray collision hardening enabled.
3. Train with the single randomized curriculum first:
   - Basic random narrow
   - Basic random medium
   - Basic random wide
   - Full random wide
   - Random wide return-home
4. Do not advance a stage on scalar success unless the selected rollout proves grasp, lift, carry, physical placement, release, settle, and no penetration/sliding.
5. If using HER, keep the HER reward sparse and goal-compatible; put richer shaping/diagnostics in a non-HER reward lane or in `info`-based gates that are not relabeled incorrectly.
6. Review the first successful rollout video from each stage, not just episode 0.

## Open Implementation Items

- Add explicit contact-distance telemetry for tray wall/object contacts if MuJoCo bindings expose it reliably.
- Add sustained-contact and airborne-latch diagnostics to `fetch_training.py` eval metadata.
- Add visual-gate criteria for valid grasp/lift/carry/release/settle using telemetry thresholds.
- Consider splitting reward into `goal_reward`, `behavior_reward`, and `safety_penalty` fields in logs so exploit paths are easier to debug.
