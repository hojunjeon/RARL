from __future__ import annotations

import math
from pathlib import Path

from PIL import Image, ImageDraw

from robotrl.agents.q_learning import QLearningAgent
from robotrl.envs.robot_arm import RobotArmReachEnv


def render_robot_arm_rollout_gif(
    *,
    checkpoint: dict[str, object],
    output_path: Path,
    max_steps: int,
    seed: int,
) -> Path:
    env_meta = dict(checkpoint["env"])  # type: ignore[index]
    if env_meta.get("name") != "RobotArmReachEnv":
        raise ValueError("robot arm video rendering requires a RobotArmReachEnv checkpoint")

    target_values = env_meta.get("target", [])
    target = tuple(int(value) for value in target_values)
    env = RobotArmReachEnv(
        joint_bins=int(env_meta["joint_bins"]),
        max_steps=max_steps,
        target=(target[0], target[1]),
        seed=seed,
    )
    agents = {
        agent_id: QLearningAgent.from_snapshot(snapshot)
        for agent_id, snapshot in dict(checkpoint["agents"]).items()  # type: ignore[index]
    }

    frames = []
    observations = env.reset()
    frames.append(_draw_robot_arm_frame(env, "start"))
    done = False
    while not done:
        actions = {
            agent_id: agents[agent_id].act(observations[agent_id], explore=False)
            for agent_id in env.agent_ids
        }
        observations, _rewards, done, info = env.step(actions)
        label = "success" if bool(info["success"]) else f"step {info['step']}"
        frames.append(_draw_robot_arm_frame(env, label))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    frames[0].save(output_path, save_all=True, append_images=frames[1:], duration=350, loop=0)
    return output_path


def _draw_robot_arm_frame(env: RobotArmReachEnv, label: str) -> Image.Image:
    width = 480
    height = 360
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    base = (width // 2, height - 58)
    link = 96
    shoulder_angle = _bin_to_angle(env.joints["shoulder"], env.joint_bins, -120, -35)
    elbow_angle = _bin_to_angle(env.joints["elbow"], env.joint_bins, -80, 80)
    target_shoulder, target_elbow = env.target or (0, 0)
    target_angles = (
        _bin_to_angle(target_shoulder, env.joint_bins, -120, -35),
        _bin_to_angle(target_elbow, env.joint_bins, -80, 80),
    )

    elbow = _segment_endpoint(base, link, shoulder_angle)
    wrist = _segment_endpoint(elbow, link, shoulder_angle + elbow_angle)
    target_elbow_xy = _segment_endpoint(base, link, target_angles[0])
    target_wrist = _segment_endpoint(target_elbow_xy, link, target_angles[0] + target_angles[1])

    draw.line((base, target_elbow_xy, target_wrist), fill=(210, 210, 210), width=4)
    draw.ellipse(_circle(target_wrist, 7), fill=(218, 66, 66))
    draw.line((base, elbow, wrist), fill=(45, 95, 165), width=8)
    draw.ellipse(_circle(base, 10), fill=(40, 40, 40))
    draw.ellipse(_circle(elbow, 9), fill=(70, 130, 190))
    draw.ellipse(_circle(wrist, 9), fill=(40, 170, 120))

    distance = env._joint_distance()
    draw.text((18, 16), f"RobotArmReachEnv | {label}", fill=(20, 20, 20))
    draw.text((18, 40), f"shoulder={env.joints['shoulder']} elbow={env.joints['elbow']}", fill=(20, 20, 20))
    draw.text((18, 64), f"target={env.target} distance={distance}", fill=(20, 20, 20))
    draw.text((18, height - 28), "gray: target pose | blue: learned greedy rollout", fill=(80, 80, 80))
    return image


def _bin_to_angle(value: int, bins: int, low_degrees: float, high_degrees: float) -> float:
    if bins == 1:
        return math.radians(low_degrees)
    ratio = value / (bins - 1)
    return math.radians(low_degrees + ratio * (high_degrees - low_degrees))


def _segment_endpoint(origin: tuple[int, int], length: int, angle: float) -> tuple[int, int]:
    return (
        int(round(origin[0] + math.cos(angle) * length)),
        int(round(origin[1] + math.sin(angle) * length)),
    )


def _circle(center: tuple[int, int], radius: int) -> tuple[int, int, int, int]:
    return (
        center[0] - radius,
        center[1] - radius,
        center[0] + radius,
        center[1] + radius,
    )
