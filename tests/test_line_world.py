import unittest

from robotrl.envs.line_world import LineWorldEnv


class LineWorldEnvTest(unittest.TestCase):
    def test_reset_returns_one_observation_per_agent(self):
        env = LineWorldEnv(length=5, max_steps=8, agent_count=2, seed=123)

        observations = env.reset()

        self.assertEqual(set(observations), {"agent_0", "agent_1"})
        self.assertEqual(observations["agent_0"], (0, 2, 4, 2))
        self.assertEqual(observations["agent_1"], (4, 2, 0, 2))

    def test_step_moves_agents_and_reports_team_success(self):
        env = LineWorldEnv(length=3, max_steps=5, agent_count=2, seed=123)
        env.reset()

        observations, rewards, done, info = env.step({"agent_0": 1, "agent_1": -1})

        self.assertTrue(done)
        self.assertTrue(info["success"])
        self.assertEqual(observations["agent_0"], (1, 1, 1, 1))
        self.assertEqual(observations["agent_1"], (1, 1, 1, 1))
        self.assertGreater(rewards["agent_0"], 0)
        self.assertGreater(rewards["agent_1"], 0)


if __name__ == "__main__":
    unittest.main()
