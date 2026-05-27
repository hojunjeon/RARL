import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from robotrl.improvement_loop import ImprovementLoopConfig, run_improvement_loop


class ImprovementLoopTest(unittest.TestCase):
    def test_loop_retries_until_agent_calls_succeed_and_logs_improvement(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "loop"
            handoff_log = Path(tmp) / "handoff.md"

            result = run_improvement_loop(
                ImprovementLoopConfig(
                    output_dir=output_dir,
                    handoff_log_path=handoff_log,
                    max_iterations=3,
                    initial_score=20,
                    target_score=30,
                    fail_first_planner_call=True,
                )
            )

            self.assertTrue(result.success)
            self.assertEqual(result.iterations_completed, 1)
            self.assertGreaterEqual(result.final_score, 30)
            self.assertTrue((output_dir / "improvement_loop_state.json").exists())

            state = json.loads((output_dir / "improvement_loop_state.json").read_text(encoding="utf-8"))
            self.assertEqual([agent["role"] for agent in state["agents"]], ["planner", "implementer", "judge"])
            self.assertGreaterEqual(state["agent_call_attempts"]["planner"], 2)
            self.assertEqual(state["decisions"][0]["orchestrator_action"], "accept_improvement")

            handoff = handoff_log.read_text(encoding="utf-8")
            self.assertIn("## 001", handoff)
            self.assertIn("Multi-agent improvement loop", handoff)
            self.assertIn("### 요청", handoff)
            self.assertIn("### 개선 기록", handoff)
            self.assertIn("score 20 -> 35", handoff)

    def test_loop_records_rejected_iteration_when_judge_finds_no_gain(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = run_improvement_loop(
                ImprovementLoopConfig(
                    output_dir=Path(tmp) / "loop",
                    handoff_log_path=Path(tmp) / "handoff.md",
                    max_iterations=1,
                    initial_score=20,
                    target_score=90,
                    simulated_gain=0,
                )
            )

            self.assertFalse(result.success)
            self.assertEqual(result.final_score, 20)
            self.assertEqual(result.iterations_completed, 1)
            self.assertIn("reject_no_improvement", result.decisions[-1]["orchestrator_action"])

    def test_cli_improve_loop_starts_harness_and_writes_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "loop"
            handoff_log = Path(tmp) / "handoff.md"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "improve-loop",
                    "--output-dir",
                    str(output_dir),
                    "--handoff-log-path",
                    str(handoff_log),
                    "--initial-score",
                    "20",
                    "--target-score",
                    "30",
                    "--simulated-gain",
                    "15",
                    "--fail-first-planner-call",
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("state=", completed.stdout)
            self.assertIn("success=True", completed.stdout)
            self.assertIn("final_score=35", completed.stdout)
            self.assertTrue((output_dir / "improvement_loop_state.json").exists())

    def test_loop_raises_when_agent_call_never_succeeds(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "loop"
            with self.assertRaisesRegex(RuntimeError, "planner agent did not succeed"):
                run_improvement_loop(
                    ImprovementLoopConfig(
                        output_dir=output_dir,
                        handoff_log_path=Path(tmp) / "handoff.md",
                        max_call_attempts=1,
                        fail_first_planner_call=True,
                    )
                )
            state = json.loads((output_dir / "improvement_loop_state.json").read_text(encoding="utf-8"))
            self.assertFalse(state["success"])
            self.assertEqual(state["failed_role"], "planner")
            self.assertEqual(state["call_history"][0]["status"], "retryable_error")

    def test_cli_improve_loop_defaults_reach_success(self):
        with tempfile.TemporaryDirectory() as tmp:
            output_dir = Path(tmp) / "loop"
            handoff_log = Path(tmp) / "handoff.md"

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "improve-loop",
                    "--output-dir",
                    str(output_dir),
                    "--handoff-log-path",
                    str(handoff_log),
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("success=True", completed.stdout)
            self.assertIn("final_score=80", completed.stdout)
            self.assertTrue((output_dir / "improvement_loop_state.json").exists())


if __name__ == "__main__":
    unittest.main()
