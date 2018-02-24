import functools
import itertools

from pirl import agents, irl

# Experiments
EXPERIMENTS = {
    # ONLY FOR TESTING CODE! Not real experiments.
    'dummy-test': {
        #TODO: change to be a fixed environment and allow overloading
        #reward? This is closer to the semantic meaning we want to express,
        #but is awkward to go with Gym's abstraction.
        'environments': ['pirl/GridWorld-Simple-v0'],
        'rl': 'value_iteration',
        'irl': ['max_ent_single', 'max_ent_population'],
        'num_trajectories': [100, 10],
    },
    'dummy-test-deterministic': {
        'environments': ['pirl/GridWorld-Simple-Deterministic-v0'],
        'rl': 'value_iteration',
        'irl': ['max_ent_single', 'max_ent_population'],
        'num_trajectories': [100, 10],
    },
    # Real experiments below
    'jungle': {
        'environments': ['pirl/GridWorld-Jungle-9x9-{}-v0'.format(k)
                         for k in ['Soda', 'Water', 'Liquid']],
        'rl': 'value_iteration',
        'irl': [
            'max_ent_single',
            'max_ent_population_reg0',
            'max_ent_population_reg0.001'
            'max_ent_population_reg0.01'
            'max_ent_population_reg0.1'
        ],
        'num_trajectories': [200, 100, 50, 30, 20, 10],
    },
    'jungle-fussy': {
        'environments': ['pirl/GridWorld-Jungle-{}-v0'.format(k)
                         for k in ['Soda', 'Water']],
        'rl': 'value_iteration',
        'irl': ['max_ent_single', 'max_ent_population'],
        'num_trajectories': [200, 100, 50, 30, 20, 10],
    },
}

# RL Algorithms
RL_ALGORITHMS = {
    # Values take form (gen_policy, compute_value).
    # Both functions take a gym.Env as their single argument.
    # compute_value moreover takes as the second argument a return value from
    # gen_policy, which may have been computed on an environment with a
    # different reward.
    'value_iteration': (lambda env: agents.tabular.value_iteration(env)[0],
                        agents.tabular.value_of_policy)
}

# IRL Algorithms
def traditional_to_single(f):
    @functools.wraps(f)
    def helper(envs, trajectories, **kwargs):
        #TODO: parallelize
        res = {k: f(envs[k], v, **kwargs) for k, v in trajectories.items()}
        values = {k: v[0] for k, v in res.items()}
        info = {k: v[1] for k, v in res.items()}
        return values, info
    return helper


def traditional_to_concat(f):
    @functools.wraps(f)
    def helper(envs, trajectories, **kwargs):
        concat_trajectories = itertools.chain(*trajectories.values())
        # Pick an environment arbitrarily. In the typical use case,
        # they are all the same up to reward anyway.
        env = list(envs.values())[0]
        value, info = f(env, concat_trajectories, **kwargs)
        value = {k: value for k in trajectories.keys()}
        return value, info
    return helper


TRADITIONAL_IRL_ALGORITHMS = {
    'max_ent': functools.partial(irl.tabular_maxent.maxent_irl, discount=0.99),
}

MY_IRL_ALGORITHMS = dict()
for reg in [0, 1e-3, 1e-2, 1e-1]:
    fn = functools.partial(irl.tabular_maxent.maxent_population_irl,
                           discount=0.99,
                           individual_reg=reg)
    MY_IRL_ALGORITHMS['max_ent_population_reg{}'.format(reg)] = fn
MY_IRL_ALGORITHMS['max_ent_population'] = MY_IRL_ALGORITHMS['max_ent_population_reg0']

IRL_ALGORITHMS = dict()
IRL_ALGORITHMS.update(MY_IRL_ALGORITHMS)
for name, algo in TRADITIONAL_IRL_ALGORITHMS.items():
    IRL_ALGORITHMS[name + '_single'] = traditional_to_single(algo)
    IRL_ALGORITHMS[name + '_concat'] = traditional_to_concat(algo)