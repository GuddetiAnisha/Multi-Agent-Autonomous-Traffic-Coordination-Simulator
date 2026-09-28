from rl_explainability import (
    ACTIONS,
    QLearningAgent,
    RLState,
    TrafficRLEnv,
    compare_explanations,
    feature_importance_explanation,
    temporal_policy_decomposition,
)


def trained_agent():
    env = TrafficRLEnv(seed=7, horizon=15)
    agent = QLearningAgent(seed=7, epsilon=0.25)
    rewards = agent.train(env, episodes=120)
    return env, agent, rewards


def test_training_runs_and_records_rewards():
    env, agent, rewards = trained_agent()
    assert len(rewards) == 120
    assert agent.q


def test_greedy_action_is_valid():
    env, agent, _ = trained_agent()
    state = RLState(2, 1, 1)
    assert agent.choose_action(state, explore=False) in ACTIONS


def test_feature_importance_is_bounded():
    env, agent, _ = trained_agent()
    values = feature_importance_explanation(agent, RLState(2, 1, 1))
    assert set(values) == {
        "queue_level",
        "conflict_level",
        "utilization_level",
    }
    assert all(0.0 <= value <= 1.0 for value in values.values())
    assert sum(values.values()) <= 1.0002


def test_tpd_returns_requested_horizon():
    env, agent, _ = trained_agent()
    outcomes = temporal_policy_decomposition(
        agent,
        env,
        RLState(2, 1, 1),
        horizon=3,
    )
    assert len(outcomes) == 3
    assert all("predicted_reward" in row for row in outcomes)


def test_combined_explanation_contains_fi_and_tpd():
    env, agent, _ = trained_agent()
    explanation = compare_explanations(agent, env, RLState(2, 2, 1))
    assert "feature_importance" in explanation
    assert "temporal_policy_decomposition" in explanation
    assert explanation["selected_action"] in ACTIONS
