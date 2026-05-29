from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

FETCH_BOX_PLACE_ENV_ID = "RobotRLFetchBoxPlace-v0"
FETCH_BOX_PLACE_DENSE_ENV_ID = "RobotRLFetchBoxPlaceDense-v0"
FETCH_BOX_PLACE_CURRICULUM_ENV_ID = "RobotRLFetchBoxPlaceCurriculum-v0"
FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID = "RobotRLFetchBoxPlaceRightCurriculum-v0"
FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID = "RobotRLFetchBoxPlaceBasicCurriculum-v0"
FETCH_BOX_PLACE_RETURN_HOME_ENV_ID = "RobotRLFetchBoxPlaceReturnHome-v0"
FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID = "RobotRLFetchBoxPlaceBasicRandomNarrow-v0"
FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID = "RobotRLFetchBoxPlaceBasicRandomMedium-v0"
FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID = "RobotRLFetchBoxPlaceBasicRandomWide-v0"
FETCH_BOX_PLACE_RANDOM_WIDE_ENV_ID = "RobotRLFetchBoxPlaceRandomWide-v0"
FETCH_BOX_PLACE_RANDOM_WIDE_RETURN_HOME_ENV_ID = "RobotRLFetchBoxPlaceRandomWideReturnHome-v0"
FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID = "RobotRLFetchBoxPlaceTwoSequential-v0"
FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID = "RobotRLFetchBoxPlaceTwoSequentialBasicCued-v0"
FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID = "RobotRLFetchBoxPlaceTwoSequentialCued-v0"
FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_BASIC_CUED_ENV_ID = (
    "RobotRLFetchBoxPlaceTwoSequentialOverWallBasicCued-v0"
)
FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID = (
    "RobotRLFetchBoxPlaceTwoSequentialOverWallObject0BasicCued-v0"
)
FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID = (
    "RobotRLFetchBoxPlaceTwoSequentialOverWallObject1BasicCued-v0"
)
FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID = (
    "RobotRLFetchBoxPlaceTwoSequentialOverWallObject1LiftCued-v0"
)
FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID = "RobotRLFetchBoxPlaceTwoSequentialOverWallCued-v0"
FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID = "RobotRLFetchBoxPlaceTwoSequentialReturnHome-v0"
FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID = "RobotRLFetchBoxPlaceTwoSequentialReturnHomeCued-v0"
FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID = (
    "RobotRLFetchBoxPlaceTwoSequentialOverWallReturnHomeCued-v0"
)
FETCH_BOX_PLACE_MAX_EPISODE_STEPS = 100
FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS = 150
RIGHT_BOX_CENTER_XY = (1.42, 0.92)
CURRICULUM_OBJECT_START_XY = (1.30, 0.75)
TWO_OBJECT_START_XYS = ((1.27, 0.75), (1.35, 0.75))
TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY = ((0.0, 0.0), (0.0, 0.055))


def compute_return_home_reward_component(diagnostics: dict[str, float]) -> float:
    """Reward returning home only after the object satisfies the final placement gate."""
    final_success = float(diagnostics.get("final_success", 0.0))
    if final_success < 1.0:
        return 0.0
    home_distance = float(diagnostics["home_distance"])
    return_home_success = float(diagnostics.get("return_home_success", 0.0))
    return 1.5 - (2.5 * home_distance) + (2.0 * return_home_success)


class RobotRLFetchBoxPlaceEnv:
    """Fetch pick-and-place task with a fixed table box placement target."""

    def __new__(cls, *args: Any, **kwargs: Any) -> object:
        try:
            from gymnasium.utils.ezpickle import EzPickle
            from gymnasium_robotics.envs.fetch.fetch_env import MujocoFetchEnv
            from gymnasium_robotics.utils import rotations
        except Exception as exc:  # pragma: no cover - dependency surface is validated elsewhere.
            raise RuntimeError("RobotRLFetchBoxPlaceEnv requires gymnasium-robotics Fetch dependencies") from exc

        class _RobotRLFetchBoxPlaceEnv(MujocoFetchEnv, EzPickle):
            def __init__(
                self,
                reward_type: str = "sparse",
                box_center_xy: tuple[float, float] = RIGHT_BOX_CENTER_XY,
                box_half_size: float = 0.035,
                height_tolerance: float = 0.03,
                success_mode: str = "final",
                basic_box_half_size: float = 0.065,
                basic_height_tolerance: float = 0.075,
                object_start_range: float = 0.15,
                object_start_center_xy: tuple[float, float] | None = None,
                object_start_radius: float = 0.025,
                home_success_distance: float = 0.06,
                object_names: tuple[str, ...] = ("object0",),
                object_start_centers_xy: tuple[tuple[float, float], ...] | None = None,
                object_goal_offsets_xy: tuple[tuple[float, float], ...] | None = None,
                model_asset_name: str = "fetch_box_place.xml",
                include_active_object_cue: bool = False,
                require_over_wall_entry: bool = False,
                require_release_for_success: bool = False,
                release_withdraw_distance: float = 0.14,
                required_object_names: tuple[str, ...] | None = None,
                preplaced_valid_object_names: tuple[str, ...] = (),
                over_wall_entry_height: float = 0.095,
                over_wall_entry_half_size: float = 0.105,
                active_lift_success_height: float | None = None,
                **env_kwargs: Any,
            ) -> None:
                if success_mode not in {
                    "final",
                    "basic",
                    "final_return_home",
                    "multi_basic",
                    "multi_final",
                    "multi_final_return_home",
                    "multi_active_lift",
                }:
                    raise ValueError(
                        "success_mode must be 'final', 'basic', 'final_return_home', "
                        "'multi_basic', 'multi_final', 'multi_final_return_home', or 'multi_active_lift'"
                    )
                self.box_center_xy = np.array(box_center_xy, dtype=np.float64)
                self.box_half_size = float(box_half_size)
                self.height_tolerance = float(height_tolerance)
                self.success_mode = success_mode
                self.basic_box_half_size = float(basic_box_half_size)
                self.basic_height_tolerance = float(basic_height_tolerance)
                self.object_start_range = float(object_start_range)
                self.include_active_object_cue = bool(include_active_object_cue)
                self.require_release_for_success = bool(require_release_for_success)
                self.release_withdraw_distance = float(release_withdraw_distance)
                self.object_start_center_xy = (
                    None if object_start_center_xy is None else np.array(object_start_center_xy, dtype=np.float64)
                )
                self.object_start_radius = float(object_start_radius)
                self.home_success_distance = float(home_success_distance)
                self.object_names = tuple(object_names)
                self.require_over_wall_entry = bool(require_over_wall_entry)
                self.required_object_names = tuple(required_object_names or object_names)
                self.preplaced_valid_object_names = tuple(preplaced_valid_object_names)
                self.over_wall_entry_height = float(over_wall_entry_height)
                self.over_wall_entry_half_size = float(over_wall_entry_half_size)
                self.active_lift_success_height = (
                    float(active_lift_success_height)
                    if active_lift_success_height is not None
                    else float(over_wall_entry_height)
                )
                self._valid_box_entry_by_object = {object_name: False for object_name in self.object_names}
                if not self.object_names:
                    raise ValueError("object_names must not be empty")
                unknown_required = set(self.required_object_names) - set(self.object_names)
                if unknown_required:
                    raise ValueError(f"required_object_names must be a subset of object_names: {unknown_required}")
                unknown_preplaced = set(self.preplaced_valid_object_names) - set(self.object_names)
                if unknown_preplaced:
                    raise ValueError(
                        f"preplaced_valid_object_names must be a subset of object_names: {unknown_preplaced}"
                    )
                if object_start_centers_xy is None:
                    self.object_start_centers_xy = None
                else:
                    if len(object_start_centers_xy) != len(self.object_names):
                        raise ValueError("object_start_centers_xy must match object_names")
                    self.object_start_centers_xy = tuple(
                        np.array(center_xy, dtype=np.float64) for center_xy in object_start_centers_xy
                    )
                if object_goal_offsets_xy is None:
                    self.object_goal_offsets_xy = None
                else:
                    if len(object_goal_offsets_xy) != len(self.object_names):
                        raise ValueError("object_goal_offsets_xy must match object_names")
                    self.object_goal_offsets_xy = tuple(
                        np.array(offset_xy, dtype=np.float64) for offset_xy in object_goal_offsets_xy
                    )
                initial_qpos = {
                    "robot0:slide0": 0.405,
                    "robot0:slide1": 0.48,
                    "robot0:slide2": 0.0,
                }
                for object_name in self.object_names:
                    initial_qpos[f"{object_name}:joint"] = [1.25, 0.53, 0.4, 1.0, 0.0, 0.0, 0.0]
                model_path = str(Path(__file__).resolve().parent / "assets" / model_asset_name)
                MujocoFetchEnv.__init__(
                    self,
                    model_path=model_path,
                    has_object=True,
                    block_gripper=False,
                    n_substeps=20,
                    gripper_extra_height=0.2,
                    target_in_the_air=False,
                    target_offset=0.0,
                    obj_range=self.object_start_range,
                    target_range=0.0,
                    distance_threshold=self.height_tolerance,
                    initial_qpos=initial_qpos,
                    reward_type=reward_type,
                    **env_kwargs,
                )
                EzPickle.__init__(
                    self,
                    reward_type=reward_type,
                    box_center_xy=box_center_xy,
                    box_half_size=box_half_size,
                    height_tolerance=height_tolerance,
                    success_mode=success_mode,
                    basic_box_half_size=basic_box_half_size,
                    basic_height_tolerance=basic_height_tolerance,
                    object_start_range=object_start_range,
                    object_start_center_xy=object_start_center_xy,
                    object_start_radius=object_start_radius,
                    home_success_distance=home_success_distance,
                    object_names=object_names,
                    object_start_centers_xy=object_start_centers_xy,
                    object_goal_offsets_xy=object_goal_offsets_xy,
                    model_asset_name=model_asset_name,
                    include_active_object_cue=include_active_object_cue,
                    require_over_wall_entry=require_over_wall_entry,
                    require_release_for_success=require_release_for_success,
                    release_withdraw_distance=release_withdraw_distance,
                    required_object_names=required_object_names,
                    preplaced_valid_object_names=preplaced_valid_object_names,
                    over_wall_entry_height=over_wall_entry_height,
                    over_wall_entry_half_size=over_wall_entry_half_size,
                    active_lift_success_height=active_lift_success_height,
                    **env_kwargs,
                )
                self.target_in_the_air = False
                self.target_range = 0.0
                self.distance_threshold = self.height_tolerance

            def _sample_goal(self) -> np.ndarray:
                goal = self.initial_gripper_xpos[:3].copy()
                goal[:2] = self.box_center_xy
                goal[2] = self.height_offset
                return goal.copy()

            def _reset_sim(self) -> bool:
                self._valid_box_entry_by_object = {object_name: False for object_name in self.object_names}
                if self.object_start_center_xy is None and self.object_start_centers_xy is None:
                    return super()._reset_sim()

                self._mujoco.mj_resetData(self.model, self.data)
                self.data.time = self.initial_time
                self.data.qpos[:] = np.copy(self.initial_qpos)
                self.data.qvel[:] = np.copy(self.initial_qvel)
                if self.model.na != 0:
                    self.data.act[:] = None

                for index, object_name in enumerate(self.object_names):
                    if self.object_start_centers_xy is not None:
                        center_xy = self.object_start_centers_xy[index]
                    else:
                        center_xy = self.object_start_center_xy
                    object_qpos = self._utils.get_joint_qpos(self.model, self.data, f"{object_name}:joint")
                    assert object_qpos.shape == (7,)
                    object_qpos[:2] = center_xy + self.np_random.uniform(
                        -self.object_start_radius,
                        self.object_start_radius,
                        size=2,
                    )
                    self._utils.set_joint_qpos(self.model, self.data, f"{object_name}:joint", object_qpos)
                self._apply_preplaced_valid_objects()
                self._mujoco.mj_forward(self.model, self.data)
                return True

            def generate_mujoco_observations(self) -> tuple[np.ndarray, ...]:
                grip_pos = self._utils.get_site_xpos(self.model, self.data, "robot0:grip")

                dt = self.n_substeps * self.model.opt.timestep
                grip_velp = self._utils.get_site_xvelp(self.model, self.data, "robot0:grip") * dt

                robot_qpos, robot_qvel = self._utils.robot_get_obs(
                    self.model,
                    self.data,
                    self._model_names.joint_names,
                )
                if self.has_object:
                    active_object_name = self._active_object_name()
                    object_pos = self._utils.get_site_xpos(self.model, self.data, active_object_name)
                    object_rot = rotations.mat2euler(
                        self._utils.get_site_xmat(self.model, self.data, active_object_name)
                    )
                    object_velp = self._utils.get_site_xvelp(self.model, self.data, active_object_name) * dt
                    object_velr = self._utils.get_site_xvelr(self.model, self.data, active_object_name) * dt
                    object_rel_pos = object_pos - grip_pos
                    object_velp -= grip_velp
                else:
                    object_pos = object_rot = object_velp = object_velr = object_rel_pos = np.zeros(0)
                gripper_state = robot_qpos[-2:]
                gripper_vel = robot_qvel[-2:] * dt
                return (
                    grip_pos,
                    object_pos,
                    object_rel_pos,
                    gripper_state,
                    object_rot,
                    object_velp,
                    object_velr,
                    grip_velp,
                    gripper_vel,
                )

            def _get_obs(self) -> dict[str, np.ndarray]:
                obs = super()._get_obs()
                if obs["desired_goal"].shape[-1] >= 3:
                    obs["desired_goal"] = self._object_goal_position(
                        self._active_object_name(),
                        obs["desired_goal"],
                    )
                if self.include_active_object_cue:
                    cue = np.zeros(len(self.object_names), dtype=np.float64)
                    cue[self._active_object_index()] = 1.0
                    obs["observation"] = np.concatenate([obs["observation"], cue]).copy()
                return obs

            def compute_reward(
                self,
                achieved_goal: np.ndarray,
                goal: np.ndarray,
                info: dict[str, Any],
            ) -> np.ndarray | float:
                success = self._is_success(achieved_goal, goal)
                if self.reward_type == "sparse":
                    return -(success < 1.0).astype(np.float32)
                achieved_goal = np.asarray(achieved_goal)
                goal = np.asarray(goal)
                return -np.linalg.norm(achieved_goal - goal, axis=-1)

            def step(self, action: np.ndarray) -> tuple[dict[str, np.ndarray], float, bool, bool, dict[str, Any]]:
                obs, reward, terminated, truncated, info = super().step(action)
                self._update_valid_box_entries()
                diagnostics = self._placement_diagnostics(obs)
                info.update(diagnostics)
                if self.success_mode in {"multi_basic", "multi_final", "multi_final_return_home"}:
                    obs = self._get_obs()
                    diagnostics = self._placement_diagnostics(obs)
                    info.update(diagnostics)
                if self.reward_type == "dense":
                    reward = self._compute_shaped_reward(obs, diagnostics)
                return obs, float(reward), terminated, truncated, info

            def _placement_diagnostics(self, obs: dict[str, np.ndarray]) -> dict[str, float]:
                observation = obs["observation"]
                gripper_pos = observation[:3]
                object_pos = obs["achieved_goal"]
                goal_pos = obs["desired_goal"]
                object_goal_distance = float(np.linalg.norm(object_pos - goal_pos))
                object_goal_xy_distance = float(np.linalg.norm(object_pos[:2] - goal_pos[:2]))
                object_height_error = float(abs(object_pos[2] - goal_pos[2]))
                gripper_object_distance = float(np.linalg.norm(gripper_pos - object_pos))
                object_lift = float(max(0.0, object_pos[2] - self.height_offset))
                gripper_opening = float(np.mean(observation[9:11]))
                gripper_goal_xy_distance = float(np.linalg.norm(gripper_pos[:2] - goal_pos[:2]))
                inside_box = float(self._inside_box(object_pos, goal_pos, self.basic_box_half_size))
                basic_success = float(self._basic_is_success(object_pos, goal_pos))
                final_success = float(self._final_is_success(object_pos, goal_pos))
                release_gate = float(
                    gripper_object_distance >= 0.075
                    and gripper_opening >= 0.025
                    and gripper_goal_xy_distance >= self.release_withdraw_distance
                )
                basic_release_success = basic_success * release_gate
                final_release_success = final_success * release_gate
                home_distance = float(np.linalg.norm(gripper_pos - self.initial_gripper_xpos))
                return_home_success = float(home_distance <= self.home_success_distance)
                place_return_success = float(final_success and return_home_success and self._tray_collision_enabled())
                tray_collision_enabled = float(self._tray_collision_enabled())
                is_success = float(self._is_success(object_pos, goal_pos))
                diagnostics = {
                    "object_goal_distance": object_goal_distance,
                    "object_goal_xy_distance": object_goal_xy_distance,
                    "object_height_error": object_height_error,
                    "gripper_object_distance": gripper_object_distance,
                    "object_lift": object_lift,
                    "gripper_opening": gripper_opening,
                    "gripper_goal_xy_distance": gripper_goal_xy_distance,
                    "inside_box": inside_box,
                    "basic_success": basic_success,
                    "final_success": final_success,
                    "basic_release_success": basic_release_success,
                    "final_release_success": final_release_success,
                    "home_distance": home_distance,
                    "return_home_success": return_home_success,
                    "place_return_success": place_return_success,
                    "geometric_is_success": final_success,
                    "tray_collision_enabled": tray_collision_enabled,
                    "physical_is_success": is_success,
                    "is_success": is_success,
                }
                if self.success_mode in {"multi_basic", "multi_final", "multi_final_return_home", "multi_active_lift"}:
                    diagnostics.update(self._multi_object_diagnostics(self.goal.copy()))
                    if self.success_mode == "multi_active_lift":
                        diagnostics["is_success"] = diagnostics["active_lift_success"]
                        diagnostics["physical_is_success"] = diagnostics["active_lift_success"]
                    elif self.success_mode == "multi_final_return_home":
                        diagnostics["is_success"] = diagnostics["multi_place_return_success"]
                        diagnostics["physical_is_success"] = diagnostics["multi_place_return_success"]
                    else:
                        diagnostics["is_success"] = diagnostics["multi_place_success"]
                        diagnostics["physical_is_success"] = diagnostics["multi_place_success"]
                return diagnostics

            def _compute_shaped_reward(self, obs: dict[str, np.ndarray], diagnostics: dict[str, float]) -> float:
                object_goal_distance = diagnostics["object_goal_distance"]
                object_goal_xy_distance = diagnostics["object_goal_xy_distance"]
                object_height_error = diagnostics["object_height_error"]
                gripper_object_distance = diagnostics["gripper_object_distance"]
                object_lift = diagnostics["object_lift"]
                is_success = diagnostics["is_success"]

                near_object = max(0.0, 1.0 - gripper_object_distance / 0.12)
                prelift_place_weight = 0.35 if object_lift < 0.025 and is_success == 0.0 else 1.0
                reach_reward = -1.0 * gripper_object_distance
                place_reward = prelift_place_weight * (
                    -2.4 * object_goal_distance - 1.4 * object_goal_xy_distance - 0.5 * object_height_error
                )
                grasp_bonus = 0.45 * near_object
                if gripper_object_distance < 0.055:
                    grasp_bonus += 0.35
                controlled_lift = min(object_lift / 0.08, 1.0)
                lift_bonus = 1.25 * controlled_lift
                if gripper_object_distance < 0.075:
                    lift_bonus += 1.0 * controlled_lift
                carry_height_bonus = 0.35 if 0.035 <= object_lift <= 0.11 else 0.0
                under_lift_penalty = 0.0
                if gripper_object_distance < 0.04 and object_goal_xy_distance > self.box_half_size * 2.0:
                    under_lift_penalty = -0.45 * max(0.0, 0.04 - object_lift) / 0.04
                if object_lift < 0.025 and is_success == 0.0:
                    under_lift_penalty -= 0.2 * near_object * max(0.0, 0.025 - object_lift) / 0.025
                over_lift_penalty = -4.0 * max(0.0, object_lift - 0.12)
                lower_near_tray_bonus = 0.4 * max(0.0, 1.0 - object_height_error / 0.08)
                if object_goal_xy_distance > self.box_half_size * 2.0:
                    lower_near_tray_bonus *= 0.25
                placed_for_release = diagnostics["basic_success"] if self.success_mode == "basic" else diagnostics["final_success"]
                if self.success_mode in {"multi_basic", "multi_final", "multi_final_return_home"}:
                    placed_for_release = diagnostics["all_required_objects_in_box"]
                release_bonus = 0.0
                post_place_contact_penalty = 0.0
                if placed_for_release >= 1.0:
                    gripper_opening = diagnostics["gripper_opening"]
                    home_distance = diagnostics["home_distance"]
                    release_distance = min(gripper_object_distance / 0.12, 1.0)
                    release_opening = min(max(gripper_opening, 0.0) / 0.035, 1.0)
                    home_progress = max(0.0, 1.0 - home_distance / 0.30)
                    release_bonus = 1.25 * release_distance + 0.85 * release_opening + 0.75 * home_progress
                    if gripper_object_distance < 0.055:
                        post_place_contact_penalty = -1.4 * (1.0 - gripper_object_distance / 0.055)
                tray_bonus = 4.0 * is_success
                if self.success_mode == "final_return_home":
                    tray_bonus += compute_return_home_reward_component(diagnostics)
                elif self.success_mode in {"multi_basic", "multi_final"}:
                    tray_bonus += 1.5 * diagnostics["objects_in_box_count"]
                    tray_bonus += 4.0 * diagnostics["all_objects_in_box"]
                elif self.success_mode == "multi_final_return_home":
                    tray_bonus += 1.5 * diagnostics["objects_in_box_count"]
                    tray_bonus += compute_return_home_reward_component(
                        {
                            "final_success": diagnostics["all_objects_in_box"],
                            "home_distance": diagnostics["home_distance"],
                            "return_home_success": diagnostics["return_home_success"],
                        }
                    )
                elif self.success_mode == "multi_active_lift":
                    active_lift_progress = min(object_lift / self.active_lift_success_height, 1.0)
                    tray_bonus += 3.0 * active_lift_progress
                    tray_bonus += 4.0 * diagnostics["active_lift_success"]
                if self.require_over_wall_entry:
                    tray_bonus += 0.8 * min(object_lift / self.over_wall_entry_height, 1.0)
                    tray_bonus += 1.0 * diagnostics["valid_box_entry_count"]
                    tray_bonus += 0.8 * diagnostics["active_object_over_wall_clearance"]
                return float(
                    place_reward
                    + reach_reward
                    + grasp_bonus
                    + lift_bonus
                    + carry_height_bonus
                    + under_lift_penalty
                    + over_lift_penalty
                    + lower_near_tray_bonus
                    + release_bonus
                    + post_place_contact_penalty
                    + tray_bonus
                )

            def _tray_geom_ids(self) -> tuple[int, ...]:
                return tuple(
                    self._model_names.geom_name2id[name]
                    for name in self._model_names.geom_names
                    if name.startswith("box_tray0:")
                )

            def _tray_collision_enabled(self) -> bool:
                tray_geom_ids = self._tray_geom_ids()
                if len(tray_geom_ids) != 5:
                    return False
                return bool(
                    np.all(self.model.geom_contype[list(tray_geom_ids)] != 0)
                    and np.all(self.model.geom_conaffinity[list(tray_geom_ids)] != 0)
                )

            def _inside_box(
                self,
                achieved_goal: np.ndarray,
                desired_goal: np.ndarray,
                half_size: float,
            ) -> np.ndarray:
                achieved_goal = np.asarray(achieved_goal)
                desired_goal = np.asarray(desired_goal)
                xy_delta = np.abs(achieved_goal[..., :2] - desired_goal[..., :2])
                return np.all(xy_delta <= half_size, axis=-1).astype(np.float32)

            def _inside_basic_vertical_envelope(
                self,
                achieved_goal: np.ndarray,
                desired_goal: np.ndarray,
            ) -> np.ndarray:
                achieved_goal = np.asarray(achieved_goal)
                desired_goal = np.asarray(desired_goal)
                z_delta = np.abs(achieved_goal[..., 2] - desired_goal[..., 2])
                return (z_delta <= self.basic_height_tolerance).astype(np.float32)

            def _basic_is_success(self, achieved_goal: np.ndarray, desired_goal: np.ndarray) -> np.ndarray:
                return np.logical_and(
                    self._inside_box(achieved_goal, desired_goal, self.basic_box_half_size),
                    self._inside_basic_vertical_envelope(achieved_goal, desired_goal),
                ).astype(np.float32)

            def _final_is_success(self, achieved_goal: np.ndarray, desired_goal: np.ndarray) -> np.ndarray:
                achieved_goal = np.asarray(achieved_goal)
                desired_goal = np.asarray(desired_goal)
                z_delta = np.abs(achieved_goal[..., 2] - desired_goal[..., 2])
                return np.logical_and(
                    self._inside_box(achieved_goal, desired_goal, self.box_half_size),
                    z_delta <= self.height_tolerance,
                ).astype(np.float32)

            def _geometric_is_success(self, achieved_goal: np.ndarray, desired_goal: np.ndarray) -> np.ndarray:
                return self._final_is_success(achieved_goal, desired_goal)

            def _release_success(
                self,
                achieved_goal: np.ndarray,
                desired_goal: np.ndarray,
                *,
                placement_success: np.ndarray | float,
            ) -> np.ndarray:
                gripper_pos = self._utils.get_site_xpos(self.model, self.data, "robot0:grip")
                robot_qpos, _robot_qvel = self._utils.robot_get_obs(
                    self.model,
                    self.data,
                    self._model_names.joint_names,
                )
                gripper_opening = float(np.mean(robot_qpos[-2:]))
                gripper_object_distance = np.linalg.norm(gripper_pos - np.asarray(achieved_goal), axis=-1)
                gripper_goal_xy_distance = np.linalg.norm(gripper_pos[:2] - np.asarray(desired_goal)[..., :2], axis=-1)
                released = np.logical_and(
                    gripper_object_distance >= 0.075,
                    gripper_opening >= 0.025,
                )
                withdrawn = gripper_goal_xy_distance >= self.release_withdraw_distance
                return np.asarray(
                    np.logical_and(np.logical_and(placement_success, released), withdrawn),
                    dtype=np.float32,
                )

            def _object_position(self, object_name: str) -> np.ndarray:
                return self._utils.get_site_xpos(self.model, self.data, object_name).copy()

            def _object_goal_position(self, object_name: str, goal: np.ndarray | None = None) -> np.ndarray:
                object_goal = self.goal.copy() if goal is None else np.asarray(goal, dtype=np.float64).copy()
                if self.object_goal_offsets_xy is not None:
                    index = self.object_names.index(object_name)
                    object_goal[:2] = object_goal[:2] + self.object_goal_offsets_xy[index]
                return object_goal

            def _set_object_xy(self, object_name: str, xy: np.ndarray) -> None:
                object_qpos = self._utils.get_joint_qpos(self.model, self.data, f"{object_name}:joint")
                assert object_qpos.shape == (7,)
                object_qpos[:2] = np.asarray(xy, dtype=np.float64)
                self._utils.set_joint_qpos(self.model, self.data, f"{object_name}:joint", object_qpos)

            def _set_object_xyz(self, object_name: str, xyz: np.ndarray) -> None:
                object_qpos = self._utils.get_joint_qpos(self.model, self.data, f"{object_name}:joint")
                assert object_qpos.shape == (7,)
                object_qpos[:3] = np.asarray(xyz, dtype=np.float64)
                self._utils.set_joint_qpos(self.model, self.data, f"{object_name}:joint", object_qpos)

            def _apply_preplaced_valid_objects(self) -> None:
                if not self.preplaced_valid_object_names:
                    return
                goal = self._sample_goal()
                for object_name in self.preplaced_valid_object_names:
                    object_goal = self._object_goal_position(object_name, goal)
                    object_goal[2] = float(self.height_offset)
                    self._set_object_xyz(object_name, object_goal)
                    self._valid_box_entry_by_object[object_name] = True

            def _object_cleared_box_wall(self, object_pos: np.ndarray, goal: np.ndarray) -> bool:
                entry_height = float(self.height_offset + self.over_wall_entry_height)
                return bool(
                    self._inside_box(object_pos, goal, self.over_wall_entry_half_size)
                    and float(object_pos[2]) >= entry_height
                )

            def _update_valid_box_entries(self) -> None:
                if not self.require_over_wall_entry:
                    for object_name in self.object_names:
                        self._valid_box_entry_by_object[object_name] = True
                    return
                goal = self.goal.copy()
                if goal.shape[-1] < 3:
                    return
                for object_name in self.object_names:
                    if self._valid_box_entry_by_object.get(object_name, False):
                        continue
                    object_pos = self._object_position(object_name)
                    if self._object_cleared_box_wall(object_pos, self._object_goal_position(object_name, goal)):
                        self._valid_box_entry_by_object[object_name] = True

            def _object_in_box_flags(self) -> tuple[float, ...]:
                self._update_valid_box_entries()
                goal = self.goal.copy()
                if goal.shape[-1] < 3:
                    return tuple(0.0 for _object_name in self.object_names)
                success_fn = self._basic_is_success if self.success_mode == "multi_basic" else self._final_is_success
                flags = []
                for object_name in self.object_names:
                    in_box = float(
                        success_fn(
                            self._object_position(object_name),
                            self._object_goal_position(object_name, goal),
                        )
                    )
                    if self.require_over_wall_entry and not self._valid_box_entry_by_object.get(object_name, False):
                        in_box = 0.0
                    flags.append(in_box)
                return tuple(flags)

            def _active_object_index(self) -> int:
                for index, in_box in enumerate(self._object_in_box_flags()):
                    if in_box < 1.0:
                        return index
                return len(self.object_names) - 1

            def _active_object_name(self) -> str:
                return self.object_names[self._active_object_index()]

            def _multi_object_diagnostics(self, goal_pos: np.ndarray) -> dict[str, float]:
                flags = self._object_in_box_flags()
                objects_in_box_count = float(sum(flags))
                all_objects_in_box = float(objects_in_box_count == len(self.object_names))
                required_flags = [
                    flags[index]
                    for index, object_name in enumerate(self.object_names)
                    if object_name in self.required_object_names
                ]
                required_objects_in_box_count = float(sum(required_flags))
                all_required_objects_in_box = float(
                    required_objects_in_box_count == len(self.required_object_names)
                )
                return_home_success = float(self._current_return_home_success())
                active_object_name = self._active_object_name()
                active_object_pos = self._object_position(active_object_name)
                active_object_goal = self._object_goal_position(active_object_name, goal_pos)
                active_object_over_wall_clearance = float(self._object_cleared_box_wall(active_object_pos, active_object_goal))
                active_object_lift = float(max(0.0, active_object_pos[2] - self.height_offset))
                active_lift_success = float(active_object_lift >= self.active_lift_success_height)
                valid_box_entry_count = float(
                    sum(1.0 for object_name in self.object_names if self._valid_box_entry_by_object.get(object_name, False))
                )
                multi_place_success = float(all_required_objects_in_box and self._tray_collision_enabled())
                multi_place_return_success = float(
                    all_required_objects_in_box and return_home_success and self._tray_collision_enabled()
                )
                diagnostics: dict[str, float] = {
                    "object_count": float(len(self.object_names)),
                    "required_object_count": float(len(self.required_object_names)),
                    "objects_in_box_count": objects_in_box_count,
                    "required_objects_in_box_count": required_objects_in_box_count,
                    "active_object_index": float(self._active_object_index()),
                    "all_objects_in_box": all_objects_in_box,
                    "all_required_objects_in_box": all_required_objects_in_box,
                    "multi_place_success": multi_place_success,
                    "multi_place_return_success": multi_place_return_success,
                    "physical_entry_required": float(self.require_over_wall_entry),
                    "success_requires_valid_box_entry": float(self.success_mode != "multi_active_lift"),
                    "valid_box_entry_count": valid_box_entry_count,
                    "active_object_over_wall_clearance": active_object_over_wall_clearance,
                    "active_object_lift": active_object_lift,
                    "active_lift_success": active_lift_success,
                    "geometric_is_success": all_objects_in_box,
                }
                for index, object_name in enumerate(self.object_names):
                    object_pos = self._object_position(object_name)
                    object_goal = self._object_goal_position(object_name, goal_pos)
                    diagnostics[f"{object_name}_in_box"] = flags[index]
                    diagnostics[f"{object_name}_valid_box_entry"] = float(
                        self._valid_box_entry_by_object.get(object_name, False)
                    )
                    diagnostics[f"{object_name}_required"] = float(object_name in self.required_object_names)
                    diagnostics[f"{object_name}_goal_distance"] = float(np.linalg.norm(object_pos - object_goal))
                return diagnostics

            def _multi_is_success(self) -> np.ndarray:
                flags = self._object_in_box_flags()
                all_required_objects_in_box = all(
                    flags[index] >= 1.0
                    for index, object_name in enumerate(self.object_names)
                    if object_name in self.required_object_names
                )
                if self.success_mode == "multi_final_return_home":
                    all_required_objects_in_box = all_required_objects_in_box and bool(
                        self._current_return_home_success()
                    )
                return np.array(all_required_objects_in_box and self._tray_collision_enabled(), dtype=np.float32)

            def _current_return_home_success(self) -> np.ndarray:
                gripper_pos = self._utils.get_site_xpos(self.model, self.data, "robot0:grip")
                return np.array(
                    np.linalg.norm(gripper_pos - self.initial_gripper_xpos) <= self.home_success_distance,
                    dtype=np.float32,
                )

            def _is_success(self, achieved_goal: np.ndarray, desired_goal: np.ndarray) -> np.ndarray:
                if self.success_mode == "basic":
                    geometric_success = self._basic_is_success(achieved_goal, desired_goal)
                    if self.require_release_for_success:
                        geometric_success = self._release_success(
                            achieved_goal,
                            desired_goal,
                            placement_success=geometric_success,
                        )
                elif self.success_mode == "final_return_home":
                    geometric_success = np.logical_and(
                        self._final_is_success(achieved_goal, desired_goal),
                        self._current_return_home_success(),
                    ).astype(np.float32)
                elif self.success_mode == "multi_active_lift":
                    active_object_pos = self._object_position(self._active_object_name())
                    active_object_lift = float(max(0.0, active_object_pos[2] - self.height_offset))
                    geometric_success = np.array(active_object_lift >= self.active_lift_success_height, dtype=np.float32)
                elif self.success_mode in {"multi_basic", "multi_final", "multi_final_return_home"}:
                    geometric_success = self._multi_is_success()
                else:
                    geometric_success = self._final_is_success(achieved_goal, desired_goal)
                    if self.require_release_for_success:
                        geometric_success = self._release_success(
                            achieved_goal,
                            desired_goal,
                            placement_success=geometric_success,
                        )
                return np.logical_and(
                    geometric_success,
                    self._tray_collision_enabled(),
                ).astype(np.float32)

        return _RobotRLFetchBoxPlaceEnv(*args, **kwargs)


def register_robotrl_fetch_envs() -> None:
    from gymnasium.envs.registration import register, registry

    if FETCH_BOX_PLACE_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            max_episode_steps=FETCH_BOX_PLACE_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_final",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "model_asset_name": "fetch_box_place_two.xml",
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_final",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_final",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "object_goal_offsets_xy": TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY,
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
                "require_over_wall_entry": True,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_BASIC_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_BASIC_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_basic",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "basic_box_half_size": 0.065,
                "basic_height_tolerance": 0.075,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "object_goal_offsets_xy": TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY,
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
                "require_over_wall_entry": True,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_basic",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "basic_box_half_size": 0.065,
                "basic_height_tolerance": 0.075,
                "object_names": ("object0", "object1"),
                "required_object_names": ("object0",),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "object_goal_offsets_xy": TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY,
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
                "require_over_wall_entry": True,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_basic",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "basic_box_half_size": 0.065,
                "basic_height_tolerance": 0.075,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "object_goal_offsets_xy": TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY,
                "preplaced_valid_object_names": ("object0",),
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
                "require_over_wall_entry": True,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_active_lift",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "object_goal_offsets_xy": TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY,
                "preplaced_valid_object_names": ("object0",),
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
                "require_over_wall_entry": True,
                "active_lift_success_height": 0.075,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_basic",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "basic_box_half_size": 0.065,
                "basic_height_tolerance": 0.075,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_final_return_home",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "model_asset_name": "fetch_box_place_two.xml",
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_final_return_home",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "multi_final_return_home",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_names": ("object0", "object1"),
                "object_start_centers_xy": TWO_OBJECT_START_XYS,
                "object_start_radius": 0.005,
                "object_goal_offsets_xy": TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY,
                "model_asset_name": "fetch_box_place_two.xml",
                "include_active_object_cue": True,
                "require_over_wall_entry": True,
            },
            max_episode_steps=FETCH_BOX_PLACE_TWO_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_DENSE_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_DENSE_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={"reward_type": "dense"},
            max_episode_steps=FETCH_BOX_PLACE_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_CURRICULUM_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_CURRICULUM_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_start_center_xy": CURRICULUM_OBJECT_START_XY,
                "object_start_radius": 0.02,
            },
            max_episode_steps=FETCH_BOX_PLACE_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_start_center_xy": CURRICULUM_OBJECT_START_XY,
                "object_start_radius": 0.02,
            },
            max_episode_steps=FETCH_BOX_PLACE_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "basic",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "basic_box_half_size": 0.065,
                "basic_height_tolerance": 0.075,
                "object_start_center_xy": CURRICULUM_OBJECT_START_XY,
                "object_start_radius": 0.02,
            },
            max_episode_steps=FETCH_BOX_PLACE_MAX_EPISODE_STEPS,
        )
    if FETCH_BOX_PLACE_RETURN_HOME_ENV_ID not in registry:
        register(
            id=FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
            entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
            kwargs={
                "reward_type": "dense",
                "success_mode": "final_return_home",
                "box_center_xy": RIGHT_BOX_CENTER_XY,
                "object_start_center_xy": CURRICULUM_OBJECT_START_XY,
                "object_start_radius": 0.02,
            },
            max_episode_steps=FETCH_BOX_PLACE_MAX_EPISODE_STEPS,
        )
    random_curriculum_specs = (
        (
            FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID,
            {
                "success_mode": "basic",
                "require_release_for_success": True,
                "basic_box_half_size": 0.065,
                "basic_height_tolerance": 0.075,
                "object_start_radius": 0.02,
            },
        ),
        (
            FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID,
            {
                "success_mode": "basic",
                "require_release_for_success": True,
                "basic_box_half_size": 0.065,
                "basic_height_tolerance": 0.075,
                "object_start_radius": 0.05,
            },
        ),
        (
            FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID,
            {
                "success_mode": "basic",
                "require_release_for_success": True,
                "basic_box_half_size": 0.065,
                "basic_height_tolerance": 0.075,
                "object_start_radius": 0.08,
            },
        ),
        (
            FETCH_BOX_PLACE_RANDOM_WIDE_ENV_ID,
            {
                "require_release_for_success": True,
                "object_start_radius": 0.08,
            },
        ),
        (
            FETCH_BOX_PLACE_RANDOM_WIDE_RETURN_HOME_ENV_ID,
            {
                "success_mode": "final_return_home",
                "object_start_radius": 0.08,
            },
        ),
    )
    for env_id, kwargs in random_curriculum_specs:
        if env_id not in registry:
            register(
                id=env_id,
                entry_point="robotrl.fetch_envs:RobotRLFetchBoxPlaceEnv",
                kwargs={
                    "reward_type": "dense",
                    "box_center_xy": RIGHT_BOX_CENTER_XY,
                    "object_start_center_xy": CURRICULUM_OBJECT_START_XY,
                    **kwargs,
                },
                max_episode_steps=FETCH_BOX_PLACE_MAX_EPISODE_STEPS,
            )
