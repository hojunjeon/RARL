import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from robotrl.harness import TrainingConfig, train
from robotrl.envs.robot_arm import RobotArmReachEnv


class RobotArmReachEnvTest(unittest.TestCase):
    def test_reset_returns_joint_control_observations(self):
        env = RobotArmReachEnv(joint_bins=5, max_steps=10, target=(3, 1), seed=123)

        observations = env.reset()

        self.assertEqual(set(observations), {"shoulder", "elbow"})
        self.assertEqual(observations["shoulder"], (0, 2, 3, 1, 4))
        self.assertEqual(observations["elbow"], (2, 0, 3, 1, 4))

    def test_step_reports_success_when_joints_reach_target(self):
        env = RobotArmReachEnv(joint_bins=5, max_steps=10, target=(1, 1), seed=123)
        env.reset()

        observations, rewards, done, info = env.step({"shoulder": 1, "elbow": -1})

        self.assertTrue(done)
        self.assertTrue(info["success"])
        self.assertEqual(observations["shoulder"], (1, 1, 1, 1, 0))
        self.assertEqual(observations["elbow"], (1, 1, 1, 1, 0))
        self.assertEqual(info["joint_distance"], 0)
        self.assertEqual(info["end_effector_distance"], 0)
        self.assertGreater(rewards["shoulder"], 0)
        self.assertGreater(rewards["elbow"], 0)


class RobotArmTrainingTest(unittest.TestCase):
    def test_robot_arm_training_writes_metrics_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = train(
                TrainingConfig(
                    env_name="robot_arm",
                    episodes=80,
                    max_steps=10,
                    seed=7,
                    output_dir=Path(tmp),
                )
            )

            metrics_path = Path(tmp) / "metrics.json"
            checkpoint_path = Path(tmp) / "policy.json"

            self.assertTrue(metrics_path.exists())
            self.assertTrue(checkpoint_path.exists())
            self.assertGreaterEqual(result.metrics["success_rate_last_10"], 0.8)
            self.assertLessEqual(result.metrics["mean_end_effector_distance_last_10"], 1.0)

            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["env_name"], "robot_arm")
            self.assertEqual(checkpoint["env"]["name"], "RobotArmReachEnv")
            self.assertEqual(sorted(checkpoint["agents"]), ["elbow", "shoulder"])

    def test_robot_arm_training_writes_early_mid_late_videos(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = train(
                TrainingConfig(
                    env_name="robot_arm",
                    episodes=60,
                    max_steps=10,
                    seed=7,
                    output_dir=Path(tmp),
                )
            )

            expected_names = {
                "early_rollout.gif",
                "mid_rollout.gif",
                "late_rollout.gif",
            }
            self.assertEqual({path.name for path in result.video_paths}, expected_names)
            for video_path in result.video_paths:
                self.assertTrue(video_path.exists())
                self.assertEqual(video_path.read_bytes()[:6], b"GIF89a")

    def test_cli_train_supports_robot_arm_env(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "train",
                    "--env",
                    "robot_arm",
                    "--episodes",
                    "40",
                    "--seed",
                    "7",
                    "--output-dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("success_rate_last_10=", completed.stdout)
            self.assertTrue((Path(tmp) / "metrics.json").exists())
            self.assertTrue((Path(tmp) / "policy.json").exists())


if __name__ == "__main__":
    unittest.main()
