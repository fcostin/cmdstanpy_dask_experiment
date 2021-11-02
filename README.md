dask & cmdstanpy experiment
===========================


![ci test badge](https://github.com/fcostin/cmdstanpy_dask_experiment/actions/workflows/test.yml/badge.svg)


### Purpose

Proof-of-concept experiment illustrating how to combine [dask distributed](http://distributed.dask.org) with the [cmdstanpy](https://github.com/stan-dev/cmdstanpy) interface to the [Stan](https://mc-stan.org/) statistical modelling platform.

### Running the demo locally

Clone this repo with `git`.

Ensure you have `docker` and `docker-compose` available on the PATH in your environment, and that your environment allows `docker` and `docker-compose` to connect to the internet to pull base images and download packages from PyPI and github.

Run `./demo.sh`. This will

1.  use docker to build a container image named `cmdstanpy_dask:dev` from `cmdstanpy_dask.Dockerfile`
2.  use docker-compose to bring up the following services:
    1.  scheduler -- running the dask-scheduler
    2.  worker -- running the dask-worker (four replicas)
    3.  client -- this will run `python client.py`

Once the services start and `client.py` establishes a dask client connection to the dask scheduler server, `client.py` will submit a number of jobs to build (trivial) Stan models and then sample them to estimate the value of a Bernoulli distribution parameter.

Once `client.py` finishes you will need to hit `CTRL^C` to interrupt `docker-compose` and tell it to bring down the services.

### How this demo works

CmdStanPy and Dask have different designs, that do not align naturally with each other:

*	Dask wants to distribute and execute a directed graph of pure-functional functions across n worker machines
*	CmdStanPy assumes each model can read and write a bunch of things to the local filesystem. State (compiled models, sampler output) is stored in the filesystem, not as simple data values in memory.

By default, if you attempt to use Dask to compile a CmdStanPy model on machine A, then distribute the model value to machine B and then sample from that model on machine B, it doesn't work, as machine B tries to read the filesytem paths stored internally in the model, but then cannot find those files as the machines have different filesystems.

In order to coerce CmdStanPy models into working when distributed between different filesystems and processes with Dask, we wrap wrap each CmdStanPy model with a wrapper object that also holds a copy of the compiled Stan model binary file in memory. Then when we distribute the wrapper object value to another machine when executing work with Dask, the receiving machine gets a copy of the model binary bytes, and we can write that Stan model binary into a temporary directory, and mess around with the internals of the recieved copy of the CmdStanPy model to point to that new location in the new filesystem.  This probably isn't very reliable, but it works!

