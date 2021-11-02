import argparse
import cmdstanpy
import dask
import dask.distributed
import json
import logging
import numpy
import numpy.random
import os
import os.path
import stat
import tempfile
import typing


def parse_args():
    p = argparse.ArgumentParser()
    p.add_argument('scheduler_address', type=str, nargs=1, help='dask scheduler address, as host:port string')
    return p.parse_args()


def get_logger():
    logger = logging.getLogger('dask_demo')
    if len(logger.handlers) == 0:
        logging.basicConfig(level=logging.INFO)
    return logger


DataDict = typing.Dict[str, typing.Hashable]
SampleResult = typing.Dict[str, typing.Hashable]


# We're parallelising things at the task level with dask, so tell
# Stan not to try to parallelise things itself.
# (otherwise a single Stan task may want to hog all cpu resources)
STAN_PARALLEL_CHAINS=1
STAN_THREADS_PER_CHAIN=1


BERNOULLI_MODEL = r"""
data {
   int<lower=0> N;
   int<lower=0,upper=1> y[N];
 }
 parameters {
   real<lower=0,upper=1> theta;
 }
 model {
   theta ~ beta(1,1);  // uniform prior on interval 0,1
   y ~ bernoulli(theta);
 }
"""


def make_bernoulli_data(rng) -> DataDict:
    n = rng.integers(low=50, high=1000)
    y = rng.uniform(low=0.0, high=1.0, size=n) < 0.7
    return {
        "N": int(n),
        "y": [int(yi) for yi in y],
    }


class DistributableStanModel:
    """
    Experimental wrapper for cmdstanpy.CmdStanModel to support
    distributing it between different machines.

    The basic idea is to figure out where cmdstanpy has written
    its compiled binary executable model to disk, then read it
    into a buffer of bytes.  Then we can send those bytes to
    another machine where we want to use the model.

    This relies on implementation details of cmdstanpy and may
    be fragile.
    """
    def __init__(self, model: cmdstanpy.CmdStanModel, model_binary: bytes):
        self.model = model
        self.model_binary = model_binary

    @staticmethod
    def compile_model(model_code: str):
        with tempfile.TemporaryDirectory() as tempdir:
            model_fn = os.path.join(tempdir, 'model.stan')
            with open(model_fn, 'w') as f_model:
                f_model.write(model_code)
            model = cmdstanpy.CmdStanModel(stan_file=model_fn)
            with open(model._exe_file, mode='rb') as f:
                model_binary = f.read()
        
        return DistributableStanModel(model, model_binary)

    def sample(self, data: DataDict, **kwargs) -> SampleResult:
        """
        sample the stan model in a temporary directory using the given data
        returns result dictionary
        """
        logger = get_logger()

        with tempfile.TemporaryDirectory() as tempdir:
            data_fn = os.path.join(tempdir, 'data.json')
            with open(data_fn, 'w') as f_data:
                json.dump(data, f_data)

            logger.info('DistributableStanModel.sample: got %d bytes of binary model data' % (len(self.model_binary), ))

            model_binary_fn = os.path.join(tempdir, 'model')
            with open(model_binary_fn, 'wb') as f_model:
                f_model.write(self.model_binary)

            # Mark the model binary as executable by current user.
            # If this is not done, cmdstanpy will fail mysteriously.
            st = os.stat(model_binary_fn)
            os.chmod(model_binary_fn, st.st_mode | stat.S_IEXEC)

            stan_model = self.model
            stan_model._exe_file = model_binary_fn

            # Specify defaults that make more sense when Stan is being
            # executed inside Dask
            sample_kwargs = {
                'parallel_chains': STAN_PARALLEL_CHAINS,
                'threads_per_chain': STAN_THREADS_PER_CHAIN,
            }
            sample_kwargs.update(kwargs)
            # Don't allow filesystem locations to be overwritten by user.
            sample_kwargs.update({
                'data': data_fn,
                'output_dir': tempdir,
            })
            fit = stan_model.sample(**sample_kwargs)

            # Stan sample() seems to be a wrapper for accessing files
            # from the output_dir, so instead of returning that directly,
            # read the outputs we want into a data structure we can return
            # to offer the caller a pure-functional API
            result = {}
            result['stan_variables'] = fit.stan_variables()
            # TODO put more things returned by fit into result
        return result


def sample(model: DistributableStanModel, data, **kwargs):
    return model.sample(data, **kwargs)


def main():
    seed = 12345
    rng = numpy.random.default_rng(seed)

    logger = get_logger()

    args = parse_args()
    logger.info('scheduler_address: %s' % (args.scheduler_address[0], ))
    client = dask.distributed.Client(address=args.scheduler_address[0])

    n_models = 20
    n_data_per_model = 50

    fits = []

    # submit graph of data construction, model construction and model fitting to dask scheduler
    for model_i in range(n_models):
            dm = client.submit(DistributableStanModel.compile_model, model_code=BERNOULLI_MODEL)
            for data_i in range(n_data_per_model):
                d = client.submit(make_bernoulli_data, rng=rng)
                f = client.submit(sample, model=dm, data=d, chains=1)
                fits.append(f)

    # read off the results
    assert len(fits) == n_models * n_data_per_model
    for fit in fits:
        result = fit.result()
        theta_draws = result['stan_variables']['theta']
        logger.info('mean(theta_draws) = %.4f' % (numpy.mean(theta_draws), ))

if __name__ == '__main__':
    main()

