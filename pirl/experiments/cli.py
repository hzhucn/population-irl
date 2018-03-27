"""
CLI app that takes a given environment and RL algorithm and:
    - 1. trains the RL algorithm on the environment (trajectories discarded).
    - 2. upon convergence, runs the RL algorithm in the environment and logs
       the resulting trajectories.


"""

import argparse
from datetime import datetime
import logging.config
from multiprocessing import Pool, current_process
import os
import pickle
import tempfile
import git

from pirl.experiments import config, experiments

logger = logging.getLogger('pirl.experiments.cli')

def _check_in(cats, kind):
    def f(s):
        if s in cats:
            return s
        else:
            raise argparse.ArgumentTypeError("'{}' is not an {}".format(s, kind))
    return f
experiment_type = _check_in(config.EXPERIMENTS.keys(), 'experiment')


def writable_dir(path):
    try:
        testfile = tempfile.TemporaryFile(dir=path)
        testfile.close()
    except OSError as e:
        desc = "Cannot write to '{}': {}".format(path, e)
        raise argparse.ArgumentTypeError(desc)

    return path


def parse_args():
    desc = 'Log trajectories from an RL algorithm.'
    parser = argparse.ArgumentParser(description=desc)
    parser.add_argument('--data_dir', metavar='dir', default='./data',
                        type=writable_dir)
    parser.add_argument('--seed', metavar='N', default=1234, type=int)
    parser.add_argument('--num-cores', metavar='N', default=None, type=int)
    parser.add_argument('experiments', metavar='experiment',
                        type=experiment_type, nargs='+')

    return parser.parse_args()


def init_worker():
    current_process().name = current_process().name.replace('ForkPoolWorker-', 'worker')
    logging.config.dictConfig(config.LOGGING)

def git_hash():
    repo = git.Repo(path=os.path.realpath(__file__),
                    search_parent_directories=True)
    return repo.head.object.hexsha


ISO_TIMESTAMP = "%Y%m%d_%H%M%S"

if __name__ == '__main__':
    args = parse_args()
    current_process().name = 'master'
    logging.config.dictConfig(config.LOGGING)
    logger.info('Starting pool')
    pool = Pool(args.num_cores, initializer=init_worker)

    for experiment in args.experiments:
        # reseed so does not matter which order experiments are run in
        timestamp = datetime.now().strftime(ISO_TIMESTAMP)
        version = git_hash()
        out_dir = '{}-{}-{}'.format(experiment, timestamp, version)
        path = os.path.join(args.data_dir, out_dir)

        res = experiments.run_experiment(experiment, pool, path, args.seed)

        logger.info('Experiment %s completed. Outcome:\n %s. Saving to %s.',
                    experiment, res['value'], path)
        with open('{}/results.pkl'.format(path), 'wb') as f:
            pickle.dump(res, f)
