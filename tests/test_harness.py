import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from robotrl.harness import TrainingConfig, train


class HarnessTest(unittest.TestCase):
    def test_train_writes_metrics_and_checkpoint(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp)

            result = train(
                TrainingConfig(
                    episodes=40,
                    max_steps=12,
                    seed=7,
                    output_dir=output_dir,
                    agent_count=2,
                    env_length=7,
                )
            )

            metrics_path = output_dir / "metrics.json"
            checkpoint_path = output_dir / "policy.json"

            self.assertTrue(metrics_path.exists())
            self.assertTrue(checkpoint_path.exists())
            self.assertEqual(result.metrics["episodes"], 40)
            self.assertEqual(result.metrics["agent_count"], 2)
            self.assertGreaterEqual(result.metrics["success_rate_last_10"], 0.7)

            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            checkpoint = json.loads(checkpoint_path.read_text(encoding="utf-8"))
            self.assertEqual(metrics["seed"], 7)
            self.assertEqual(sorted(checkpoint["agents"]), ["agent_0", "agent_1"])

    def test_training_is_seed_reproducible(self):
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            config = {
                "episodes": 20,
                "max_steps": 12,
                "seed": 11,
                "agent_count": 2,
                "env_length": 7,
            }

            first_result = train(TrainingConfig(output_dir=Path(first), **config))
            second_result = train(TrainingConfig(output_dir=Path(second), **config))

            self.assertEqual(first_result.metrics, second_result.metrics)

    def test_metrics_include_behavior_quality_fields(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = train(TrainingConfig(episodes=20, output_dir=Path(tmp), seed=5))

            self.assertIn("timeout_count", result.metrics)
            self.assertIn("mean_team_reward_last_10", result.metrics)
            self.assertIn("mean_steps_last_10", result.metrics)

    def test_cli_train_writes_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "train",
                    "--episodes",
                    "20",
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
