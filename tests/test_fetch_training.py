import json
import subprocess
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET
from pathlib import Path

import numpy as np

from robotrl.fetch_envs import (
    FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID,
    FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID,
    FETCH_BOX_PLACE_CURRICULUM_ENV_ID,
    FETCH_BOX_PLACE_DENSE_ENV_ID,
    FETCH_BOX_PLACE_ENV_ID,
    FETCH_BOX_PLACE_RANDOM_WIDE_ENV_ID,
    FETCH_BOX_PLACE_RANDOM_WIDE_RETURN_HOME_ENV_ID,
    FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
    FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
    FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
    RIGHT_BOX_CENTER_XY,
    TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY,
    CURRICULUM_OBJECT_START_XY,
    register_robotrl_fetch_envs,
)
from robotrl.fetch_training import (
    FetchLoopConfig,
    FetchTrainingConfig,
    build_fetch_loop_spec,
    curriculum_stage_decision,
    build_fetch_training_spec,
    is_success_condition_met,
    select_fetch_vec_env_name,
    train_fetch,
)
from robotrl.cli import next_run_dir
from robotrl import fetch_envs, fetch_training


class FetchTrainingConfigTest(unittest.TestCase):
    def test_fetch_box_tray_geoms_are_collidable(self):
        asset_path = Path(__file__).resolve().parents[1] / "robotrl" / "assets" / "fetch_box_place.xml"
        root = ET.parse(asset_path).getroot()
        tray_geoms = [
            geom
            for geom in root.findall(".//geom")
            if (geom.get("name") or "").startswith("box_tray0:")
        ]

        self.assertEqual(len(tray_geoms), 5)
        for geom in tray_geoms:
            self.assertNotEqual(geom.get("contype"), "0", geom.get("name"))
            self.assertNotEqual(geom.get("conaffinity"), "0", geom.get("name"))

    def test_fetch_box_tray_walls_are_tall_enough_for_curriculum_landing(self):
        asset_path = Path(__file__).resolve().parents[1] / "robotrl" / "assets" / "fetch_box_place.xml"
        root = ET.parse(asset_path).getroot()
        wall_geoms = [
            geom
            for geom in root.findall(".//geom")
            if (geom.get("name") or "").startswith("box_tray0:")
            and (geom.get("name") or "") != "box_tray0:base"
        ]

        self.assertEqual(len(wall_geoms), 4)
        for geom in wall_geoms:
            half_extents = [float(value) for value in (geom.get("size") or "").split()]
            self.assertGreaterEqual(half_extents[2], 0.04, geom.get("name"))

    def test_two_object_asset_defines_second_collidable_free_object(self):
        asset_path = Path(__file__).resolve().parents[1] / "robotrl" / "assets" / "fetch_box_place_two.xml"
        root = ET.parse(asset_path).getroot()

        object1_joint = root.find(".//joint[@name='object1:joint']")
        object1_geom = root.find(".//geom[@name='object1']")
        object1_site = root.find(".//site[@name='object1']")

        self.assertIsNotNone(object1_joint)
        self.assertEqual(object1_joint.get("type"), "free")
        self.assertIsNotNone(object1_geom)
        self.assertNotEqual(object1_geom.get("contype"), "0")
        self.assertNotEqual(object1_geom.get("conaffinity"), "0")
        self.assertIsNotNone(object1_site)

    def test_next_run_dir_uses_execution_order_numbers(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp) / "learning"
            (root / "run_001_existing").mkdir(parents=True)
            (root / "run_003_later").mkdir()

            self.assertEqual(
                next_run_dir("Fetch Loop RobotRLFetchBoxPlace-v0 seed7", root=root),
                root / "run_004_fetch_loop_robotrlfetchboxplace-v0_seed7",
            )

    def test_fetch_training_spec_uses_expected_learning_conditions(self):
        spec = build_fetch_training_spec(
            FetchTrainingConfig(
                total_timesteps=2_000_000,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
            )
        )

        self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_DENSE_ENV_ID)
        self.assertEqual(spec["algorithm"], "SAC")
        self.assertEqual(spec["policy"], "MultiInputPolicy")
        self.assertEqual(spec["replay_buffer"], "HerReplayBuffer")
        self.assertEqual(spec["n_envs"], 6)
        self.assertEqual(spec["learning_starts"], 10_000)
        self.assertEqual(spec["checkpoint_interval"], 50_000)
        self.assertFalse(spec["progress_bar"])

    def test_fetch_dry_run_writes_training_spec_without_fetch_dependencies(self):
        with tempfile.TemporaryDirectory() as tmp:
            result = train_fetch(
                FetchTrainingConfig(
                    total_timesteps=123,
                    n_envs=2,
                    output_dir=Path(tmp),
                    dry_run=True,
                )
            )

            spec_path = Path(tmp) / "fetch_training_spec.json"
            self.assertEqual(result.spec_path, spec_path)
            self.assertTrue(spec_path.exists())
            spec = json.loads(spec_path.read_text(encoding="utf-8"))
            self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_DENSE_ENV_ID)
            self.assertEqual(spec["total_timesteps"], 123)
            self.assertEqual(spec["n_envs"], 2)

    def test_cli_fetch_train_dry_run_writes_spec(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "fetch-train",
                    "--dry-run",
                    "--total-timesteps",
                    "123",
                    "--n-envs",
                    "2",
                    "--output-dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("spec=", completed.stdout)
            self.assertTrue((Path(tmp) / "fetch_training_spec.json").exists())

    def test_cli_fetch_loop_dry_run_writes_spec_and_eval_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "fetch-loop",
                    "--dry-run",
                    "--chunk-timesteps",
                    "123",
                    "--eval-episodes",
                    "3",
                    "--success-threshold",
                    "0.9",
                    "--output-dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("spec=", completed.stdout)
            self.assertIn("evals=", completed.stdout)
            self.assertTrue((Path(tmp) / "fetch_loop_spec.json").exists())
            self.assertTrue((Path(tmp) / "eval_results.json").exists())

    def test_fetch_loop_spec_records_success_gate(self):
        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/fetch_loop"),
                dry_run=True,
            )
        )

        self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_DENSE_ENV_ID)
        self.assertEqual(spec["algorithm"], "SAC")
        self.assertEqual(spec["replay_buffer"], "HerReplayBuffer")
        self.assertEqual(spec["chunk_timesteps"], 50_000)
        self.assertEqual(spec["eval_episodes"], 20)
        self.assertEqual(spec["success_threshold"], 0.8)
        self.assertTrue(spec["continue_until_success"])

    def test_right_curriculum_loop_uses_shaped_reward_replay_buffer(self):
        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                env_id=FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/fetch_loop"),
                dry_run=True,
            )
        )

        self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID)
        self.assertEqual(spec["replay_buffer"], "DictReplayBuffer")

    def test_basic_curriculum_loop_uses_dict_replay_for_staged_restart(self):
        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                env_id=FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/fetch_loop"),
                dry_run=True,
            )
        )

        self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID)
        self.assertEqual(spec["replay_buffer"], "DictReplayBuffer")

    def test_basic_to_final_curriculum_spec_records_encoded_stage_path(self):
        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                env_id=FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                curriculum_stage_env_ids=(
                    FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                    FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                ),
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/fetch_loop"),
                dry_run=True,
            )
        )

        self.assertEqual(
            spec["curriculum_stage_env_ids"],
            [
                FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
            ],
        )
        self.assertEqual(spec["initial_stage_index"], 0)
        self.assertEqual(spec["initial_stage_env_id"], FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID)
        self.assertEqual(spec["final_stage_env_id"], FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID)

    def test_final_to_return_curriculum_spec_records_resume_source(self):
        resume_from = Path("runs/learning/run_014_fetch_box_basic_to_final_curriculum_seed7/success_model.zip")
        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                env_id=FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                curriculum_stage_env_ids=(
                    FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                    FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
                ),
                resume_from=resume_from,
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/fetch_loop"),
                dry_run=True,
            )
        )

        self.assertEqual(spec["resume_from"], str(resume_from))
        self.assertEqual(
            spec["curriculum_stage_env_ids"],
            [
                FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
            ],
        )
        self.assertEqual(spec["initial_stage_env_id"], FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID)
        self.assertEqual(spec["final_stage_env_id"], FETCH_BOX_PLACE_RETURN_HOME_ENV_ID)

    def test_resume_loop_loads_model_with_run_tensorboard_log(self):
        import inspect

        from robotrl import fetch_training

        source = inspect.getsource(fetch_training._run_fetch_loop_with_dependencies)
        self.assertIn("SAC.load", source)
        self.assertIn('tensorboard_log=str(config.output_dir / "tensorboard")', source)

    def test_basic_stage_success_advances_curriculum_instead_of_stopping(self):
        self.assertEqual(
            curriculum_stage_decision(
                stage_index=0,
                stage_count=2,
                stage_success=True,
            ),
            "advance",
        )
        self.assertEqual(
            curriculum_stage_decision(
                stage_index=1,
                stage_count=2,
                stage_success=True,
            ),
            "complete",
        )
        self.assertEqual(
            curriculum_stage_decision(
                stage_index=0,
                stage_count=2,
                stage_success=False,
            ),
            "continue",
        )

    def test_cli_fetch_loop_curriculum_dry_run_records_basic_to_final_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "fetch-loop",
                    "--dry-run",
                    "--curriculum",
                    "basic-to-final",
                    "--chunk-timesteps",
                    "123",
                    "--eval-episodes",
                    "3",
                    "--success-threshold",
                    "0.8",
                    "--output-dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("spec=", completed.stdout)
            spec = json.loads((Path(tmp) / "fetch_loop_spec.json").read_text(encoding="utf-8"))
            self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID)
            self.assertEqual(
                spec["curriculum_stage_env_ids"],
                [
                    FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                    FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                ],
            )

    def test_cli_fetch_loop_dry_run_records_basic_to_final_return_resume_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            resume_from = Path("runs/learning/run_014_fetch_box_basic_to_final_curriculum_seed7/success_model.zip")
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "fetch-loop",
                    "--dry-run",
                    "--curriculum",
                    "basic-to-final-return",
                    "--resume-from",
                    str(resume_from),
                    "--chunk-timesteps",
                    "123",
                    "--eval-episodes",
                    "3",
                    "--success-threshold",
                    "0.8",
                    "--output-dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("spec=", completed.stdout)
            spec = json.loads((Path(tmp) / "fetch_loop_spec.json").read_text(encoding="utf-8"))
            self.assertEqual(spec["resume_from"], str(resume_from))
            self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID)
            self.assertEqual(
                spec["curriculum_stage_env_ids"],
                [
                    FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                    FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                    FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
                ],
            )

    def test_cli_fetch_loop_curriculum_dry_run_records_single_random_to_return_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "fetch-loop",
                    "--dry-run",
                    "--curriculum",
                    "single-random-to-return",
                    "--chunk-timesteps",
                    "123",
                    "--eval-episodes",
                    "3",
                    "--success-threshold",
                    "0.8",
                    "--output-dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("spec=", completed.stdout)
            spec = json.loads((Path(tmp) / "fetch_loop_spec.json").read_text(encoding="utf-8"))
            self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID)
            self.assertEqual(spec["replay_buffer"], "DictReplayBuffer")
            self.assertEqual(
                spec["curriculum_stage_env_ids"],
                [
                    FETCH_BOX_PLACE_BASIC_RANDOM_NARROW_ENV_ID,
                    FETCH_BOX_PLACE_BASIC_RANDOM_MEDIUM_ENV_ID,
                    FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID,
                    FETCH_BOX_PLACE_RANDOM_WIDE_ENV_ID,
                    FETCH_BOX_PLACE_RANDOM_WIDE_RETURN_HOME_ENV_ID,
                ],
            )

    def test_right_curriculum_uses_dummy_vec_env_on_windows_for_stable_restart(self):
        self.assertEqual(
            select_fetch_vec_env_name(
                env_id=FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                n_envs=6,
                platform_name="win32",
            ),
            "DummyVecEnv",
        )

    def test_basic_curriculum_uses_dummy_vec_env_on_windows_for_stable_restart(self):
        self.assertEqual(
            select_fetch_vec_env_name(
                env_id=FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID,
                n_envs=6,
                platform_name="win32",
            ),
            "DummyVecEnv",
        )

    def test_return_home_curriculum_uses_dummy_vec_env_on_windows_for_stable_restart(self):
        self.assertEqual(
            select_fetch_vec_env_name(
                env_id=FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
                n_envs=6,
                platform_name="win32",
            ),
            "DummyVecEnv",
        )

    def test_two_object_return_home_uses_dict_replay_and_dummy_vec_env(self):
        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                env_id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
                resume_from=Path("runs/learning/run_016_fetch_box_return_home_signal_seed7/success_model.zip"),
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/learning_2/run_001_multi_object_2_sequential_return_seed7"),
                dry_run=True,
            )
        )

        self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID)
        self.assertEqual(spec["replay_buffer"], "DictReplayBuffer")
        self.assertEqual(
            spec["resume_from"],
            str(Path("runs/learning/run_016_fetch_box_return_home_signal_seed7/success_model.zip")),
        )
        self.assertEqual(
            select_fetch_vec_env_name(
                env_id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
                n_envs=6,
                platform_name="win32",
            ),
            "DummyVecEnv",
        )

    def test_two_object_no_home_stage_uses_dict_replay_and_dummy_vec_env(self):
        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                env_id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
                resume_from=Path("runs/learning/run_016_fetch_box_return_home_signal_seed7/success_model.zip"),
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/learning_2/run_002_multi_object_2_curriculum_seed7"),
                dry_run=True,
            )
        )

        self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID)
        self.assertEqual(spec["replay_buffer"], "DictReplayBuffer")
        self.assertEqual(
            select_fetch_vec_env_name(
                env_id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
                n_envs=6,
                platform_name="win32",
            ),
            "DummyVecEnv",
        )

    def test_two_to_two_return_curriculum_spec_records_encoded_stage_path(self):
        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                env_id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
                curriculum_stage_env_ids=(
                    FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
                    FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
                ),
                resume_from=Path("runs/learning/run_016_fetch_box_return_home_signal_seed7/success_model.zip"),
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/learning_2/run_002_multi_object_2_curriculum_seed7"),
                dry_run=True,
            )
        )

        self.assertEqual(spec["env_id"], FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID)
        self.assertEqual(
            spec["curriculum_stage_env_ids"],
            [
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
            ],
        )
        self.assertEqual(spec["initial_stage_env_id"], FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID)
        self.assertEqual(spec["final_stage_env_id"], FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID)

    def test_two_to_two_return_curriculum_defaults_to_active_object_cue_envs(self):
        basic_cued_env_id = getattr(fetch_envs, "FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID", None)
        self.assertIsNotNone(basic_cued_env_id)

        spec = build_fetch_loop_spec(
            FetchLoopConfig(
                env_id=basic_cued_env_id,
                curriculum_stage_env_ids=(
                    basic_cued_env_id,
                    FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
                    FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
                ),
                resume_from=None,
                chunk_timesteps=50_000,
                eval_episodes=20,
                success_threshold=0.8,
                n_envs=6,
                learning_starts=10_000,
                checkpoint_interval=50_000,
                output_dir=Path("runs/learning_2/run_003_multi_object_2_active_cue_seed7"),
                dry_run=True,
            )
        )

        self.assertEqual(spec["env_id"], basic_cued_env_id)
        self.assertEqual(
            spec["curriculum_stage_env_ids"],
            [
                basic_cued_env_id,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
                FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
            ],
        )
        self.assertEqual(spec["initial_stage_env_id"], basic_cued_env_id)
        self.assertEqual(spec["final_stage_env_id"], FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID)

    def test_cli_fetch_loop_curriculum_dry_run_records_two_to_two_return_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "fetch-loop",
                    "--dry-run",
                    "--curriculum",
                    "two-to-two-return",
                    "--chunk-timesteps",
                    "123",
                    "--eval-episodes",
                    "3",
                    "--success-threshold",
                    "0.8",
                    "--output-dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("spec=", completed.stdout)
            spec = json.loads((Path(tmp) / "fetch_loop_spec.json").read_text(encoding="utf-8"))
            self.assertIsNone(spec["resume_from"])
            basic_cued_env_id = getattr(fetch_envs, "FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID", None)
            self.assertEqual(spec["env_id"], basic_cued_env_id)
            self.assertEqual(
                spec["curriculum_stage_env_ids"],
                [
                    basic_cued_env_id,
                    FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID,
                    FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_CUED_ENV_ID,
                ],
            )

    def test_cli_fetch_loop_curriculum_dry_run_records_two_over_wall_return_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "robotrl.cli",
                    "fetch-loop",
                    "--dry-run",
                    "--curriculum",
                    "two-over-wall-return",
                    "--resume-from",
                    "runs/learning_2/run_004_multi_object_2_basic_active_cue_seed7/success_model.zip",
                    "--chunk-timesteps",
                    "123",
                    "--eval-episodes",
                    "3",
                    "--success-threshold",
                    "0.8",
                    "--output-dir",
                    tmp,
                ],
                check=True,
                capture_output=True,
                text=True,
            )

            self.assertIn("spec=", completed.stdout)
            spec = json.loads((Path(tmp) / "fetch_loop_spec.json").read_text(encoding="utf-8"))
            self.assertEqual(
                spec["resume_from"],
                "runs\\learning_2\\run_004_multi_object_2_basic_active_cue_seed7\\success_model.zip",
            )
            object0_basic_env_id = getattr(
                fetch_envs,
                "FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT0_BASIC_CUED_ENV_ID",
            )
            object1_basic_env_id = getattr(
                fetch_envs,
                "FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID",
            )
            object1_lift_env_id = getattr(
                fetch_envs,
                "FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID",
            )
            self.assertEqual(spec["env_id"], object0_basic_env_id)
            self.assertEqual(
                spec["curriculum_stage_env_ids"],
                [
                    object0_basic_env_id,
                    object1_lift_env_id,
                    object1_basic_env_id,
                    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID,
                    FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID,
                ],
            )
            self.assertEqual(spec["final_stage_env_id"], FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_RETURN_HOME_CUED_ENV_ID)

    def test_two_object_over_wall_object1_stage_starts_with_object0_preplaced_and_keeps_object1_gate(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        object1_stage_env_id = getattr(
            fetch_envs,
            "FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID",
            None,
        )
        self.assertIsNotNone(object1_stage_env_id)
        register_robotrl_fetch_envs()
        env = gym.make(object1_stage_env_id)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            diagnostics = unwrapped._multi_object_diagnostics(unwrapped.goal)

            self.assertEqual(unwrapped.success_mode, "multi_basic")
            self.assertTrue(unwrapped.require_over_wall_entry)
            self.assertEqual(unwrapped._active_object_index(), 1)
            np.testing.assert_allclose(obs["observation"][-2:], np.array([0.0, 1.0]), atol=1e-6)
            self.assertEqual(diagnostics["object0_in_box"], 1.0)
            self.assertEqual(diagnostics["object0_valid_box_entry"], 1.0)
            self.assertEqual(diagnostics["object1_in_box"], 0.0)
            self.assertEqual(diagnostics["object1_valid_box_entry"], 0.0)

            object1_goal = unwrapped._object_goal_position("object1", unwrapped.goal)
            low_inside = object1_goal.copy()
            low_inside[2] = float(unwrapped.height_offset)
            unwrapped._set_object_xyz("object1", low_inside)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)

            diagnostics = unwrapped._multi_object_diagnostics(unwrapped.goal)
            self.assertEqual(diagnostics["object1_in_box"], 0.0)
            self.assertEqual(diagnostics["object1_valid_box_entry"], 0.0)
            self.assertEqual(float(unwrapped._multi_is_success()), 0.0)
        finally:
            env.close()

    def test_two_object_over_wall_object1_lift_stage_succeeds_on_lift_without_box_credit(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        object1_lift_env_id = getattr(
            fetch_envs,
            "FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_LIFT_CUED_ENV_ID",
            None,
        )
        self.assertIsNotNone(object1_lift_env_id)
        register_robotrl_fetch_envs()
        env = gym.make(object1_lift_env_id)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            self.assertEqual(unwrapped.success_mode, "multi_active_lift")
            self.assertTrue(unwrapped.require_over_wall_entry)
            self.assertEqual(unwrapped._active_object_index(), 1)
            np.testing.assert_allclose(obs["observation"][-2:], np.array([0.0, 1.0]), atol=1e-6)

            object1_start = unwrapped._object_position("object1")
            low_object1 = object1_start.copy()
            low_object1[2] = float(unwrapped.height_offset + 0.02)
            lifted_object1 = object1_start.copy()
            lifted_object1[2] = float(unwrapped.height_offset + unwrapped.active_lift_success_height + 0.005)

            unwrapped._set_object_xyz("object1", low_object1)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            low_diagnostics = unwrapped._placement_diagnostics(unwrapped._get_obs())
            self.assertEqual(low_diagnostics["is_success"], 0.0)

            unwrapped._set_object_xyz("object1", lifted_object1)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            lifted_diagnostics = unwrapped._placement_diagnostics(unwrapped._get_obs())
            self.assertEqual(lifted_diagnostics["is_success"], 1.0)
            self.assertEqual(lifted_diagnostics["object1_in_box"], 0.0)
            self.assertEqual(lifted_diagnostics["object1_valid_box_entry"], 0.0)
            self.assertEqual(lifted_diagnostics["success_requires_valid_box_entry"], 0.0)
        finally:
            env.close()

    def test_two_object_over_wall_object1_stage_rewards_active_lift_before_valid_entry_credit(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(fetch_envs.FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_OBJECT1_BASIC_CUED_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            object1_start = unwrapped._object_position("object1")
            low_object1 = object1_start.copy()
            low_object1[2] = float(unwrapped.height_offset)
            high_object1 = object1_start.copy()
            high_object1[2] = float(unwrapped.height_offset + unwrapped.over_wall_entry_height)

            unwrapped._set_object_xyz("object1", low_object1)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            low_obs = unwrapped._get_obs()
            low_diagnostics = unwrapped._placement_diagnostics(low_obs)
            low_reward = unwrapped._compute_shaped_reward(low_obs, low_diagnostics)

            unwrapped._set_object_xyz("object1", high_object1)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            high_obs = unwrapped._get_obs()
            high_diagnostics = unwrapped._placement_diagnostics(high_obs)
            high_reward = unwrapped._compute_shaped_reward(high_obs, high_diagnostics)

            self.assertGreater(high_reward - low_reward, 1.0)
            self.assertEqual(low_diagnostics["object1_in_box"], 0.0)
            self.assertEqual(high_diagnostics["object1_in_box"], 0.0)
            self.assertEqual(high_diagnostics["object1_valid_box_entry"], 0.0)
        finally:
            env.close()

    def test_two_object_over_wall_basic_stage_keeps_valid_entry_gate(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        basic_over_wall_env_id = getattr(fetch_envs, "FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_BASIC_CUED_ENV_ID", None)
        self.assertIsNotNone(basic_over_wall_env_id)
        register_robotrl_fetch_envs()
        basic_env = gym.make(basic_over_wall_env_id)
        strict_env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID)
        try:
            basic_obs, _info = basic_env.reset(seed=7)
            strict_obs, _info = strict_env.reset(seed=7)
            basic_unwrapped = basic_env.unwrapped
            strict_unwrapped = strict_env.unwrapped
            basic_goal0 = basic_unwrapped._object_goal_position("object0", basic_unwrapped.goal)
            basic_goal1 = basic_unwrapped._object_goal_position("object1", basic_unwrapped.goal)
            strict_goal0 = strict_unwrapped._object_goal_position("object0", strict_unwrapped.goal)
            strict_goal1 = strict_unwrapped._object_goal_position("object1", strict_unwrapped.goal)

            self.assertEqual(basic_obs["observation"].shape, (27,))
            self.assertEqual(strict_obs["observation"].shape, (27,))
            self.assertEqual(basic_unwrapped.success_mode, "multi_basic")
            self.assertTrue(basic_unwrapped.require_over_wall_entry)

            relaxed0 = basic_goal0 + np.array([0.055, 0.0, 0.045])
            relaxed1 = basic_goal1 + np.array([0.055, 0.0, 0.045])
            basic_unwrapped._set_object_xyz("object0", relaxed0)
            basic_unwrapped._set_object_xyz("object1", relaxed1)
            basic_unwrapped._mujoco.mj_forward(basic_unwrapped.model, basic_unwrapped.data)

            self.assertEqual(float(basic_unwrapped._multi_is_success()), 0.0)
            diagnostics = basic_unwrapped._multi_object_diagnostics(basic_unwrapped.goal)
            self.assertEqual(diagnostics["object0_valid_box_entry"], 0.0)
            self.assertEqual(diagnostics["object1_valid_box_entry"], 0.0)

            high0 = basic_goal0.copy()
            high1 = basic_goal1.copy()
            high0[2] = float(basic_unwrapped.height_offset + basic_unwrapped.over_wall_entry_height + 0.01)
            high1[2] = float(basic_unwrapped.height_offset + basic_unwrapped.over_wall_entry_height + 0.01)
            basic_unwrapped._set_object_xyz("object0", high0)
            basic_unwrapped._set_object_xyz("object1", high1)
            basic_unwrapped._mujoco.mj_forward(basic_unwrapped.model, basic_unwrapped.data)
            basic_unwrapped._update_valid_box_entries()

            basic_unwrapped._set_object_xyz("object0", relaxed0)
            basic_unwrapped._set_object_xyz("object1", relaxed1)
            basic_unwrapped._mujoco.mj_forward(basic_unwrapped.model, basic_unwrapped.data)

            self.assertEqual(float(basic_unwrapped._multi_is_success()), 1.0)
            diagnostics = basic_unwrapped._multi_object_diagnostics(basic_unwrapped.goal)
            self.assertEqual(diagnostics["object0_valid_box_entry"], 1.0)
            self.assertEqual(diagnostics["object1_valid_box_entry"], 1.0)

            strict_unwrapped._set_object_xyz("object0", strict_goal0 + np.array([0.055, 0.0, 0.045]))
            strict_unwrapped._set_object_xyz("object1", strict_goal1 + np.array([0.055, 0.0, 0.045]))
            strict_unwrapped._mujoco.mj_forward(strict_unwrapped.model, strict_unwrapped.data)
            self.assertEqual(float(strict_unwrapped._multi_is_success()), 0.0)
        finally:
            basic_env.close()
            strict_env.close()

    def test_multi_env_still_uses_subproc_vec_env_off_windows(self):
        self.assertEqual(
            select_fetch_vec_env_name(
                env_id=FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID,
                n_envs=6,
                platform_name="linux",
            ),
            "SubprocVecEnv",
        )

    def test_success_condition_uses_eval_rate_and_video(self):
        self.assertFalse(
            is_success_condition_met(
                {"success_rate": 0.8, "episodes": 20},
                video_path=Path("missing.gif"),
                threshold=0.8,
            )
        )
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "rollout.gif"
            video_path.write_bytes(b"GIF89a")
            self.assertTrue(
                is_success_condition_met(
                    {"success_rate": 0.8, "episodes": 20},
                    video_path=video_path,
                    threshold=0.8,
                )
            )

    def test_success_condition_treats_none_valid_entry_flag_as_single_object_default(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "rollout.gif"
            video_path.write_bytes(b"GIF89a")
            self.assertTrue(
                is_success_condition_met(
                    {
                        "success_rate": 0.9,
                        "episodes": 20,
                        "success_requires_valid_box_entry_rate": None,
                    },
                    video_path=video_path,
                    threshold=0.8,
                )
            )

    def test_success_condition_rejects_success_without_object1_valid_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            video_path = Path(tmp) / "rollout.gif"
            video_path.write_bytes(b"GIF89a")
            self.assertFalse(
                is_success_condition_met(
                    {
                        "success_rate": 0.8,
                        "episodes": 20,
                        "object0_valid_box_entry_rate": 0.8,
                        "object1_valid_box_entry_rate": 0.7,
                    },
                    video_path=video_path,
                    threshold=0.8,
                )
            )
            self.assertTrue(
                is_success_condition_met(
                    {
                        "success_rate": 0.8,
                        "episodes": 20,
                        "object0_valid_box_entry_rate": 0.8,
                        "object1_valid_box_entry_rate": 0.8,
                    },
                    video_path=video_path,
                    threshold=0.8,
                )
            )
            self.assertTrue(
                is_success_condition_met(
                    {
                        "success_rate": 0.8,
                        "episodes": 20,
                        "success_requires_valid_box_entry_rate": 0.0,
                        "object0_valid_box_entry_rate": 0.8,
                        "object1_valid_box_entry_rate": 0.0,
                    },
                    video_path=video_path,
                    threshold=0.8,
                )
            )
            self.assertTrue(
                is_success_condition_met(
                    {
                        "success_rate": 0.8,
                        "episodes": 20,
                        "required_object_names": ["object0"],
                        "object0_valid_box_entry_rate": 0.8,
                        "object1_valid_box_entry_rate": 0.0,
                    },
                    video_path=video_path,
                    threshold=0.8,
                )
            )

    def test_fetch_learning_starts_must_exceed_episode_horizon(self):
        with self.assertRaisesRegex(ValueError, "learning_starts"):
            train_fetch(FetchTrainingConfig(learning_starts=50, dry_run=True))

    def test_eval_summary_aggregates_return_home_diagnostics(self):
        class FakeModel:
            def predict(self, obs, deterministic=True):
                return np.zeros(4, dtype=np.float32), None

        class FakeEnv:
            def __init__(self, home_distance, return_success, place_return_success):
                self.home_distance = home_distance
                self.return_success = return_success
                self.place_return_success = place_return_success

            def reset(self, seed=None):
                return {"observation": np.zeros(3)}, {}

            def step(self, action):
                return (
                    {"observation": np.zeros(3)},
                    1.0,
                    True,
                    False,
                    {
                        "is_success": self.place_return_success,
                        "object_goal_distance": 0.02,
                        "gripper_object_distance": 0.3,
                        "object_lift": 0.0,
                        "home_distance": self.home_distance,
                        "return_home_success": self.return_success,
                        "place_return_success": self.place_return_success,
                    },
                )

            def render(self):
                return np.zeros((2, 2, 3), dtype=np.uint8)

            def close(self):
                pass

        class FakeGym:
            def __init__(self):
                self.envs = [
                    FakeEnv(home_distance=0.04, return_success=1.0, place_return_success=1.0),
                    FakeEnv(home_distance=0.16, return_success=0.0, place_return_success=0.0),
                ]

            def make(self, env_id, render_mode=None):
                return self.envs.pop(0)

        class FakeImageio:
            def mimsave(self, video_path, frames, duration, loop):
                Path(video_path).write_bytes(b"GIF89a")

        with tempfile.TemporaryDirectory() as tmp:
            record = fetch_training._evaluate_fetch_model(
                gym=FakeGym(),
                imageio=FakeImageio(),
                model=FakeModel(),
                env_id=FETCH_BOX_PLACE_RETURN_HOME_ENV_ID,
                seed=7,
                episodes=2,
                iteration=3,
                total_timesteps=750_060,
                video_path=Path(tmp) / "rollout.gif",
            )

        self.assertEqual(record["mean_home_distance"], 0.1)
        self.assertEqual(record["return_home_success_rate"], 0.5)
        self.assertEqual(record["place_return_success_rate"], 0.5)

    def test_eval_summary_aggregates_multi_object_diagnostics(self):
        class FakeModel:
            def predict(self, obs, deterministic=True):
                return np.zeros(4, dtype=np.float32), None

        class FakeEnv:
            def __init__(self, success, objects_in_box, active_index):
                self.success = success
                self.objects_in_box = objects_in_box
                self.active_index = active_index

            def reset(self, seed=None):
                return {"observation": np.zeros(25)}, {}

            def step(self, action):
                return (
                    {"observation": np.zeros(25)},
                    1.0,
                    True,
                    False,
                    {
                        "is_success": self.success,
                        "object_goal_distance": 0.02,
                        "gripper_object_distance": 0.3,
                        "object_lift": 0.0,
                        "home_distance": 0.04,
                        "return_home_success": self.success,
                        "place_return_success": self.success,
                        "object_count": 2,
                        "objects_in_box_count": self.objects_in_box,
                        "object0_in_box": 1.0,
                        "object1_in_box": self.success,
                        "active_object_index": self.active_index,
                        "all_objects_in_box": self.success,
                        "multi_place_return_success": self.success,
                        "valid_box_entry_count": self.objects_in_box,
                        "object0_valid_box_entry": 1.0,
                        "object1_valid_box_entry": self.success,
                    },
                )

            def render(self):
                return np.zeros((2, 2, 3), dtype=np.uint8)

            def close(self):
                pass

        class FakeGym:
            def __init__(self):
                self.envs = [
                    FakeEnv(success=1.0, objects_in_box=2, active_index=1),
                    FakeEnv(success=0.0, objects_in_box=1, active_index=1),
                ]

            def make(self, env_id, render_mode=None):
                return self.envs.pop(0)

        class FakeImageio:
            def mimsave(self, video_path, frames, duration, loop):
                Path(video_path).write_bytes(b"GIF89a")

        with tempfile.TemporaryDirectory() as tmp:
            record = fetch_training._evaluate_fetch_model(
                gym=FakeGym(),
                imageio=FakeImageio(),
                model=FakeModel(),
                env_id=FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID,
                seed=7,
                episodes=2,
                iteration=1,
                total_timesteps=50_000,
                video_path=Path(tmp) / "rollout.gif",
            )

        self.assertEqual(record["object_count"], 2)
        self.assertEqual(record["mean_objects_in_box_count"], 1.5)
        self.assertEqual(record["object0_in_box_rate"], 1.0)
        self.assertEqual(record["object1_in_box_rate"], 0.5)
        self.assertEqual(record["all_objects_in_box_rate"], 0.5)
        self.assertEqual(record["multi_place_return_success_rate"], 0.5)
        self.assertEqual(record["mean_valid_box_entry_count"], 1.5)
        self.assertEqual(record["object0_valid_box_entry_rate"], 1.0)
        self.assertEqual(record["object1_valid_box_entry_rate"], 0.5)

    def test_return_home_reward_improves_when_placed_object_is_held_and_gripper_moves_home(self):
        reward_component = getattr(fetch_envs, "compute_return_home_reward_component", None)
        self.assertIsNotNone(reward_component)

        far_from_home = reward_component(
            {
                "final_success": 1.0,
                "object_goal_distance": 0.02,
                "home_distance": 0.2,
                "return_home_success": 0.0,
            }
        )
        near_home = reward_component(
            {
                "final_success": 1.0,
                "object_goal_distance": 0.02,
                "home_distance": 0.04,
                "return_home_success": 1.0,
            }
        )
        object_not_placed = reward_component(
            {
                "final_success": 0.0,
                "object_goal_distance": 0.2,
                "home_distance": 0.04,
                "return_home_success": 1.0,
            }
        )

        self.assertGreater(near_home, far_from_home)
        self.assertLess(object_not_placed, near_home)


@unittest.skipUnless(
    __import__("importlib").util.find_spec("gymnasium_robotics") is not None,
    "gymnasium-robotics is not installed",
)
class FetchBoxPlaceEnvTest(unittest.TestCase):
    def test_box_place_env_places_goal_on_fixed_table_box_zone(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            self.assertFalse(unwrapped.target_in_the_air)
            self.assertEqual(unwrapped.target_range, 0.0)
            self.assertIn("box_tray0:base", unwrapped._model_names.geom_names)
            np.testing.assert_allclose(obs["desired_goal"][:2], np.array(RIGHT_BOX_CENTER_XY), atol=1e-6)
            self.assertAlmostEqual(float(obs["desired_goal"][2]), float(unwrapped.height_offset), places=6)
        finally:
            env.close()

    def test_box_success_requires_object_inside_box_zone_and_table_height(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            goal = obs["desired_goal"]
            self.assertEqual(float(unwrapped._is_success(goal, goal)), 1.0)
            outside_xy = goal + np.array([0.04, 0.0, 0.0])
            high_enough_to_fail = goal + np.array([0.0, 0.0, 0.04])
            self.assertEqual(float(unwrapped._is_success(outside_xy, goal)), 0.0)
            self.assertEqual(float(unwrapped._is_success(high_enough_to_fail, goal)), 0.0)
        finally:
            env.close()

    def test_dense_box_env_uses_distance_reward_with_same_success_gate(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_DENSE_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            goal = obs["desired_goal"]
            near = goal + np.array([0.01, 0.0, 0.0])
            far = goal + np.array([0.08, 0.0, 0.0])
            self.assertEqual(unwrapped.reward_type, "dense")
            self.assertGreater(float(unwrapped.compute_reward(near, goal, {})), float(unwrapped.compute_reward(far, goal, {})))
            self.assertEqual(float(unwrapped._is_success(far, goal)), 0.0)
        finally:
            env.close()

    def test_dense_step_reward_reports_motion_diagnostics(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_DENSE_ENV_ID)
        _obs, _info = env.reset(seed=7)
        try:
            _obs, reward, _terminated, _truncated, info = env.step(np.zeros(4, dtype=np.float32))
            self.assertIsInstance(float(reward), float)
            self.assertIn("object_goal_distance", info)
            self.assertIn("gripper_object_distance", info)
            self.assertIn("object_height_error", info)
            self.assertIn("object_lift", info)
            self.assertIn("gripper_opening", info)
            self.assertIn("tray_collision_enabled", info)
            self.assertIn("physical_is_success", info)
            self.assertIn("inside_box", info)
            self.assertIn("basic_success", info)
            self.assertIn("final_success", info)
        finally:
            env.close()

    def test_success_rejects_missing_tray_collision_contract(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        tray_geom_ids = [
            unwrapped._model_names.geom_name2id[name]
            for name in unwrapped._model_names.geom_names
            if name.startswith("box_tray0:")
        ]
        original_contype = unwrapped.model.geom_contype[tray_geom_ids].copy()
        original_conaffinity = unwrapped.model.geom_conaffinity[tray_geom_ids].copy()
        try:
            goal = obs["desired_goal"]
            self.assertEqual(float(unwrapped._is_success(goal, goal)), 1.0)
            unwrapped.model.geom_contype[tray_geom_ids] = 0
            unwrapped.model.geom_conaffinity[tray_geom_ids] = 0
            self.assertEqual(float(unwrapped._is_success(goal, goal)), 0.0)
        finally:
            unwrapped.model.geom_contype[tray_geom_ids] = original_contype
            unwrapped.model.geom_conaffinity[tray_geom_ids] = original_conaffinity
            env.close()

    def test_curriculum_env_starts_object_near_gripper_side_of_tray(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            self.assertEqual(unwrapped.reward_type, "dense")
            self.assertLess(np.linalg.norm(obs["achieved_goal"][:2] - np.array(CURRICULUM_OBJECT_START_XY)), 0.035)
            self.assertLess(obs["achieved_goal"][0], 1.345)
            np.testing.assert_allclose(obs["desired_goal"][:2], np.array(RIGHT_BOX_CENTER_XY), atol=1e-6)
        finally:
            env.close()

    def test_single_random_wide_env_samples_object_inside_wider_front_workspace(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_BASIC_RANDOM_WIDE_ENV_ID)
        try:
            positions = []
            for seed in (7, 8, 9, 10):
                obs, _info = env.reset(seed=seed)
                positions.append(obs["achieved_goal"][:2].copy())
                self.assertLessEqual(
                    np.linalg.norm(obs["achieved_goal"][:2] - np.array(CURRICULUM_OBJECT_START_XY)),
                    0.115,
                )
                np.testing.assert_allclose(obs["desired_goal"][:2], np.array(RIGHT_BOX_CENTER_XY), atol=1e-6)

            pairwise_distances = [
                np.linalg.norm(positions[index] - positions[0])
                for index in range(1, len(positions))
            ]
            self.assertTrue(any(distance > 0.02 for distance in pairwise_distances))
        finally:
            env.close()

    def test_basic_curriculum_accepts_box_footprint_and_vertical_envelope_without_weakening_final_env(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        basic_env = gym.make(FETCH_BOX_PLACE_BASIC_CURRICULUM_ENV_ID)
        final_env = gym.make(FETCH_BOX_PLACE_RIGHT_CURRICULUM_ENV_ID)
        basic_unwrapped = basic_env.unwrapped
        final_unwrapped = final_env.unwrapped
        try:
            basic_obs, _info = basic_env.reset(seed=7)
            final_obs, _info = final_env.reset(seed=7)
            basic_goal = basic_obs["desired_goal"]
            final_goal = final_obs["desired_goal"]
            placed_inside_high = basic_goal + np.array([0.055, 0.0, 0.045])

            self.assertEqual(float(basic_unwrapped._basic_is_success(placed_inside_high, basic_goal)), 1.0)
            self.assertEqual(float(basic_unwrapped._final_is_success(placed_inside_high, basic_goal)), 0.0)
            self.assertEqual(float(basic_unwrapped._is_success(placed_inside_high, basic_goal)), 1.0)
            self.assertEqual(float(final_unwrapped._is_success(placed_inside_high, final_goal)), 0.0)
        finally:
            basic_env.close()
            final_env.close()

    def test_return_home_success_requires_final_place_and_gripper_near_initial_home(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_RETURN_HOME_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            goal = obs["desired_goal"]
            initial_home = unwrapped.initial_gripper_xpos.copy()
            self.assertEqual(float(unwrapped._is_success(goal, goal)), 1.0)

            unwrapped.initial_gripper_xpos = initial_home + np.array([0.2, 0.0, 0.0])
            self.assertEqual(float(unwrapped._is_success(goal, goal)), 0.0)
            placed_obs = {key: value.copy() for key, value in obs.items()}
            placed_obs["achieved_goal"] = goal.copy()
            placed_obs["observation"][:3] = initial_home
            diagnostics = unwrapped._placement_diagnostics(placed_obs)
            self.assertIn("home_distance", diagnostics)
            self.assertIn("return_home_success", diagnostics)
            self.assertIn("place_return_success", diagnostics)
            self.assertEqual(diagnostics["final_success"], 1.0)
            self.assertEqual(diagnostics["return_home_success"], 0.0)
            self.assertEqual(diagnostics["place_return_success"], 0.0)
        finally:
            env.close()

    def test_two_object_sequential_env_resets_two_front_objects_with_compatible_observation_shape(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        single_env = gym.make(FETCH_BOX_PLACE_RETURN_HOME_ENV_ID)
        multi_env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID)
        try:
            single_obs, _info = single_env.reset(seed=7)
            multi_obs, _info = multi_env.reset(seed=7)
            unwrapped = multi_env.unwrapped
            object0 = unwrapped._object_position("object0")
            object1 = unwrapped._object_position("object1")

            self.assertEqual(unwrapped.object_names, ("object0", "object1"))
            self.assertEqual(multi_obs["observation"].shape, single_obs["observation"].shape)
            self.assertEqual(multi_obs["achieved_goal"].shape, single_obs["achieved_goal"].shape)
            self.assertLess(np.linalg.norm(object0[:2] - object1[:2]), 0.2)
            self.assertGreater(np.linalg.norm(object0[:2] - object1[:2]), 0.055)
            self.assertFalse(bool(unwrapped._final_is_success(object0, multi_obs["desired_goal"])))
            self.assertFalse(bool(unwrapped._final_is_success(object1, multi_obs["desired_goal"])))
        finally:
            single_env.close()
            multi_env.close()

    def test_two_object_cued_env_adds_active_object_one_hot_without_changing_old_env_shape(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        old_env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID)
        cued_env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID)
        try:
            old_obs, _info = old_env.reset(seed=7)
            cued_obs, _info = cued_env.reset(seed=7)
            cued_unwrapped = cued_env.unwrapped
            goal = cued_obs["desired_goal"]

            self.assertEqual(old_obs["observation"].shape, (25,))
            self.assertEqual(cued_obs["observation"].shape, (27,))
            np.testing.assert_allclose(cued_obs["observation"][-2:], np.array([1.0, 0.0]), atol=1e-6)

            cued_unwrapped._set_object_xy("object0", goal[:2])
            cued_unwrapped._mujoco.mj_forward(cued_unwrapped.model, cued_unwrapped.data)
            switched_obs = cued_unwrapped._get_obs()

            self.assertEqual(cued_unwrapped._active_object_index(), 1)
            np.testing.assert_allclose(switched_obs["observation"][-2:], np.array([0.0, 1.0]), atol=1e-6)
        finally:
            old_env.close()
            cued_env.close()

    def test_two_object_basic_cued_stage_relaxes_success_without_changing_cued_observation_shape(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        basic_cued_env_id = getattr(fetch_envs, "FETCH_BOX_PLACE_TWO_SEQUENTIAL_BASIC_CUED_ENV_ID", None)
        self.assertIsNotNone(basic_cued_env_id)
        register_robotrl_fetch_envs()
        basic_env = gym.make(basic_cued_env_id)
        strict_env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_CUED_ENV_ID)
        try:
            basic_obs, _info = basic_env.reset(seed=7)
            strict_obs, _info = strict_env.reset(seed=7)
            basic_unwrapped = basic_env.unwrapped
            strict_unwrapped = strict_env.unwrapped
            goal = basic_obs["desired_goal"]
            relaxed_inside = goal + np.array([0.055, 0.0, 0.045])

            self.assertEqual(basic_obs["observation"].shape, (27,))
            self.assertEqual(strict_obs["observation"].shape, (27,))
            self.assertEqual(basic_unwrapped.success_mode, "multi_basic")
            basic_unwrapped._set_object_xy("object0", relaxed_inside[:2])
            basic_unwrapped._set_object_xy("object1", relaxed_inside[:2])
            strict_unwrapped._set_object_xy("object0", relaxed_inside[:2])
            strict_unwrapped._set_object_xy("object1", relaxed_inside[:2])
            basic_unwrapped._mujoco.mj_forward(basic_unwrapped.model, basic_unwrapped.data)
            strict_unwrapped._mujoco.mj_forward(strict_unwrapped.model, strict_unwrapped.data)

            self.assertEqual(float(basic_unwrapped._multi_is_success()), 1.0)
            self.assertEqual(float(strict_unwrapped._multi_is_success()), 0.0)
        finally:
            basic_env.close()
            strict_env.close()

    def test_two_object_over_wall_success_rejects_direct_wall_penetration(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            base_goal = unwrapped.goal.copy()
            object0_goal = unwrapped._object_goal_position("object0", base_goal)
            object1_goal = unwrapped._object_goal_position("object1", base_goal)
            object0_direct_inside = object0_goal.copy()
            object1_direct_inside = object1_goal.copy()
            object0_direct_inside[2] = float(unwrapped.height_offset)
            object1_direct_inside[2] = float(unwrapped.height_offset)
            unwrapped._set_object_xyz("object0", object0_direct_inside)
            unwrapped._set_object_xyz("object1", object1_direct_inside)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)

            self.assertEqual(float(unwrapped._multi_is_success()), 0.0)
            diagnostics = unwrapped._multi_object_diagnostics(base_goal)
            self.assertEqual(diagnostics["all_objects_in_box"], 0.0)
            self.assertEqual(diagnostics["valid_box_entry_count"], 0.0)
            self.assertEqual(diagnostics["object0_valid_box_entry"], 0.0)
            self.assertEqual(diagnostics["object1_valid_box_entry"], 0.0)

            object0_over_wall = object0_goal.copy()
            object1_over_wall = object1_goal.copy()
            object0_over_wall[2] = float(unwrapped.height_offset + unwrapped.over_wall_entry_height + 0.01)
            object1_over_wall[2] = float(unwrapped.height_offset + unwrapped.over_wall_entry_height + 0.01)
            unwrapped._set_object_xyz("object0", object0_over_wall)
            unwrapped._set_object_xyz("object1", object1_over_wall)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            unwrapped._update_valid_box_entries()

            unwrapped._set_object_xyz("object0", object0_direct_inside)
            unwrapped._set_object_xyz("object1", object1_direct_inside)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)

            self.assertEqual(float(unwrapped._multi_is_success()), 1.0)
            diagnostics = unwrapped._multi_object_diagnostics(base_goal)
            self.assertEqual(diagnostics["all_objects_in_box"], 1.0)
            self.assertEqual(diagnostics["valid_box_entry_count"], 2.0)
            self.assertEqual(diagnostics["object0_valid_box_entry"], 1.0)
            self.assertEqual(diagnostics["object1_valid_box_entry"], 1.0)
        finally:
            env.close()

    def test_two_object_over_wall_stage_uses_separate_object_slots(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            object0_goal = unwrapped._object_goal_position("object0", unwrapped.goal)
            object1_goal = unwrapped._object_goal_position("object1", unwrapped.goal)

            np.testing.assert_allclose(
                object1_goal[:2] - object0_goal[:2],
                np.array(TWO_OBJECT_OVER_WALL_GOAL_OFFSETS_XY[1]),
                atol=1e-6,
            )
            np.testing.assert_allclose(obs["desired_goal"], object0_goal, atol=1e-6)
            self.assertGreater(np.linalg.norm(object1_goal[:2] - object0_goal[:2]), 0.05)
            self.assertEqual(float(unwrapped._final_is_success(object0_goal, object0_goal)), 1.0)
            self.assertEqual(float(unwrapped._final_is_success(object1_goal, object1_goal)), 1.0)

            high_object0 = object0_goal.copy()
            high_object0[2] = float(unwrapped.height_offset + unwrapped.over_wall_entry_height + 0.01)
            unwrapped._set_object_xyz("object0", high_object0)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            unwrapped._update_valid_box_entries()

            placed_object0 = object0_goal.copy()
            placed_object0[2] = float(unwrapped.height_offset)
            unwrapped._set_object_xyz("object0", placed_object0)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            switched_obs = unwrapped._get_obs()

            self.assertEqual(unwrapped._active_object_index(), 1)
            np.testing.assert_allclose(switched_obs["desired_goal"], object1_goal, atol=1e-6)
            np.testing.assert_allclose(switched_obs["observation"][-2:], np.array([0.0, 1.0]), atol=1e-6)

            high_object1 = object1_goal.copy()
            high_object1[2] = float(unwrapped.height_offset + unwrapped.over_wall_entry_height + 0.01)
            unwrapped._set_object_xyz("object1", high_object1)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            diagnostics = unwrapped._placement_diagnostics(unwrapped._get_obs())

            self.assertEqual(diagnostics["active_object_index"], 1.0)
            self.assertEqual(diagnostics["active_object_over_wall_clearance"], 1.0)
            self.assertAlmostEqual(
                diagnostics["object1_goal_distance"],
                float(unwrapped.over_wall_entry_height + 0.01),
            )
        finally:
            env.close()

    def test_over_wall_entry_latches_only_after_clearance_and_resets(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_OVER_WALL_CUED_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            goal = obs["desired_goal"]
            low_inside = goal.copy()
            low_inside[2] = float(unwrapped.height_offset + 0.02)
            high_inside = goal.copy()
            high_inside[2] = float(unwrapped.height_offset + unwrapped.over_wall_entry_height + 0.01)

            unwrapped._set_object_xyz("object1", low_inside)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            unwrapped._update_valid_box_entries()
            self.assertEqual(unwrapped._valid_box_entry_by_object["object1"], False)

            unwrapped._set_object_xyz("object1", high_inside)
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            unwrapped._update_valid_box_entries()
            self.assertEqual(unwrapped._valid_box_entry_by_object["object1"], True)

            env.reset(seed=8)
            self.assertEqual(unwrapped._valid_box_entry_by_object["object0"], False)
            self.assertEqual(unwrapped._valid_box_entry_by_object["object1"], False)
        finally:
            env.close()

    def test_two_object_sequential_success_requires_both_objects_in_box_and_home(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_RETURN_HOME_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            goal = obs["desired_goal"]
            self.assertEqual(float(unwrapped._multi_is_success()), 0.0)

            unwrapped._set_object_xy("object0", goal[:2])
            unwrapped._set_object_xy("object1", goal[:2] + np.array([0.12, 0.0]))
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            self.assertEqual(float(unwrapped._multi_is_success()), 0.0)
            self.assertEqual(unwrapped._active_object_index(), 1)

            unwrapped._set_object_xy("object1", goal[:2])
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            original_home = unwrapped.initial_gripper_xpos.copy()
            unwrapped.initial_gripper_xpos = original_home + np.array([0.2, 0.0, 0.0])
            self.assertEqual(float(unwrapped._multi_is_success()), 0.0)

            unwrapped.initial_gripper_xpos = original_home
            self.assertEqual(float(unwrapped._multi_is_success()), 1.0)
        finally:
            env.close()

    def test_two_object_sequential_stage_success_requires_both_objects_in_box_not_home(self):
        import gymnasium as gym
        import gymnasium_robotics  # noqa: F401

        register_robotrl_fetch_envs()
        env = gym.make(FETCH_BOX_PLACE_TWO_SEQUENTIAL_ENV_ID)
        obs, _info = env.reset(seed=7)
        unwrapped = env.unwrapped
        try:
            goal = obs["desired_goal"]
            self.assertEqual(unwrapped.success_mode, "multi_final")
            self.assertEqual(float(unwrapped._multi_is_success()), 0.0)

            unwrapped._set_object_xy("object0", goal[:2])
            unwrapped._set_object_xy("object1", goal[:2])
            unwrapped._mujoco.mj_forward(unwrapped.model, unwrapped.data)
            original_home = unwrapped.initial_gripper_xpos.copy()
            unwrapped.initial_gripper_xpos = original_home + np.array([0.2, 0.0, 0.0])

            self.assertEqual(float(unwrapped._multi_is_success()), 1.0)
            diagnostics = unwrapped._multi_object_diagnostics(goal)
            self.assertEqual(diagnostics["all_objects_in_box"], 1.0)
            self.assertEqual(diagnostics["multi_place_success"], 1.0)
            self.assertEqual(diagnostics["multi_place_return_success"], 0.0)
        finally:
            env.close()


if __name__ == "__main__":
    unittest.main()
