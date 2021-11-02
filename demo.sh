#!/bin/bash

set -x -e -o pipefail

docker build -t cmdstanpy_dask:dev -f cmdstanpy_dask.Dockerfile .

docker-compose up --scale worker=4
