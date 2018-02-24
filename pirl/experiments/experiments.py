import collections
import logging

import gym

from pirl import utils
from pirl.experiments import config

logger = logging.getLogger('pirl.experiments.experiments')

#TODO: refactor once structure is clearer
# Should this be pushed into agents package?
# Will different agents require some setup code?
def make_rl_algo(algo):
    return config.RL_ALGORITHMS[algo]


def make_irl_algo(algo):
    return config.IRL_ALGORITHMS[algo]


def sample(env, policy):
    #TODO: generalize. This is specialised to fully-observable MDPs
    # and assumes policy is a deterministic mapping from states to actions.
    # Could also use Monitor to log this -- although think it's cleaner
    # to do it directly ourselves?

    states = []
    actions = []

    state = env.reset()
    states.append(state)

    done = False
    while not done:
        action = policy[state]
        state, reward, done, _ = env.step(action)
        actions.append(action)
        states.append(state)

    return states, actions


def synthetic_data(env, policy, num_trajectories):
    trajectories = [sample(env, policy) for _i in range(num_trajectories)]
    return trajectories


class LearnedRewardWrapper(gym.Wrapper):
    """
    Wrapper for a gym.Env replacing with a new reward matrix.
    Intended for the tabular setting. Will work when the observations are
    discrete and the reward is a function of the observation.
    """
    def __init__(self, env, new_reward):
        self.new_reward = new_reward
        super().__init__(env)

    def step(self, action):
        observation, old_reward, done, info = self.env.step(action)
        #TODO: this won't work if observations are continuous?
        # (It was written only to handle the tabular setting, probably needs
        #  to be extended once we have new environments.)
        new_reward = self.new_reward[observation, action]
        return observation, new_reward, done, info

    @property
    def reward(self):
        return self.new_reward


def run_experiment(experiment, seed):
    '''Run experiment defined in config.EXPERIMENTS.

    Returns:
        tuple, (trajectories, rewards, expected_value), where:

        - trajectories: synthetic data.
            dict, keyed by environments, with values generated by synthetic_data.
        - rewards: IRL inferred reward.
            nested dict, keyed by environment then IRL algorithm.
        - expected_value: value obtained reoptimizing in the environment.
            Use the RL algorithm used to generate the original synthetic data
            to train a policy on the inferred reward, then compute expected
            discounted value obtained from the resulting policy.
        '''
    utils.random_seed(seed)
    cfg = config.EXPERIMENTS[experiment]

    # Generate synthetic data
    logger.debug('%s: creating environments %s', experiment, cfg['environments'])
    envs = collections.OrderedDict()
    for name in cfg['environments']:
        env = gym.make(name)
        env.seed(seed)
        envs[name] = env

    logger.debug('%s: generating synthetic data: training', experiment)
    gen_policy, compute_value = make_rl_algo(cfg['rl'])
    policies = collections.OrderedDict(
        (name, gen_policy(env)) for name, env in envs.items()
    )
    logger.debug('%s: generating synthetic data: sampling', experiment)
    trajectories = collections.OrderedDict(
        (k, synthetic_data(e, policies[k], cfg['num_trajectories']))
        for k, e in envs.items()
    )

    # Run IRL
    rewards = collections.OrderedDict()
    for irl_name in cfg['irl']:
        logger.debug('%s: running IRL algo: %s', experiment, irl_name)
        irl_algo = make_irl_algo(irl_name)
        rewards[irl_name] = irl_algo(envs, trajectories)

    # Evaluate results
    # Note the expected value is estimated, and the accuracy of this may depend
    # on the RL algorithm. For value iteration, for example, this is computed
    # directly; for many other algorithms, a sample-based approach is adopted.
    expected_value = {}
    for irl_name, reward in rewards.items():
        res = {}
        for env_name, r in reward.items():
            logger.debug('%s: evaluating how good %s was on %s',
                         experiment, irl_name, env_name)
            env = envs[env_name]
            wrapped_env = LearnedRewardWrapper(env, r)
            reoptimized_policy = gen_policy(wrapped_env)
            res[env_name] = compute_value(env, reoptimized_policy)
        expected_value[irl_name] = res
    ground_truth = {}
    for env_name, env in envs.items():
        ground_truth[env_name] = compute_value(env, policies[env_name])
    expected_value['ground_truth'] = ground_truth

    return {
        'trajectories': trajectories,
        'reward': rewards,
        'expected_value': expected_value,
    }
