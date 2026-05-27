import unittest

from robotrl.agents.q_learning import QLearningAgent


class QLearningAgentTest(unittest.TestCase):
    def test_update_increases_value_for_rewarded_action(self):
        agent = QLearningAgent(actions=(-1, 0, 1), learning_rate=0.5, discount=0.9, epsilon=0.0, seed=1)

        agent.update(state=("s",), action=1, reward=2.0, next_state=("next",), done=True)

        self.assertEqual(agent.act(("s",)), 1)
        self.assertAlmostEqual(agent.value(("s",), 1), 1.0)

    def test_snapshot_round_trip_preserves_policy(self):
        agent = QLearningAgent(actions=(-1, 0, 1), learning_rate=0.5, discount=0.9, epsilon=0.0, seed=1)
        agent.update(state=("s",), action=-1, reward=3.0, next_state=("next",), done=True)

        restored = QLearningAgent.from_snapshot(agent.snapshot())

        self.assertEqual(restored.act(("s",)), -1)
        self.assertAlmostEqual(restored.value(("s",), -1), 1.5)


if __name__ == "__main__":
    unittest.main()
