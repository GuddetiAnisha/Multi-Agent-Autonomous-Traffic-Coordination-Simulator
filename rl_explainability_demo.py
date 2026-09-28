from pprint import pprint

from rl_explainability import (
    QLearningAgent,
    RLState,
    TrafficRLEnv,
    compare_explanations,
)


def main():
    env = TrafficRLEnv(seed=7, horizon=20)
    agent = QLearningAgent(seed=7, epsilon=0.25)

    rewards = agent.train(env, episodes=300)
    state = RLState(queue_level=2, conflict_level=1, utilization_level=1)

    print("Mean reward over final 50 episodes:", sum(rewards[-50:]) / 50)
    pprint(compare_explanations(agent, env, state))


if __name__ == "__main__":
    main()
