FROM python:3.9-bullseye

ENV CSVER=2.28.1
ENV CMDSTAN=/opt/cmdstan-$CSVER
ENV CXX=clang++-11
ENV PYTHONDONTWRITEBYTECODE=1

RUN apt-get update && apt-get install -y clang-11
RUN pip install numpy pytest
RUN pip install --upgrade setuptools wheel

WORKDIR /opt/
RUN curl -OL https://github.com/stan-dev/cmdstan/releases/download/v$CSVER/cmdstan-$CSVER.tar.gz \
 && tar xzf cmdstan-$CSVER.tar.gz \
 && rm -rf cmdstan-$CSVER.tar.gz \
 && cd cmdstan-$CSVER \
 && make -j2 build examples/bernoulli/bernoulli

RUN pip install -e git+https://github.com/stan-dev/cmdstanpy@v1.0.0rc1#egg=cmdstanpy

RUN pip install dask distributed

RUN mkdir -p /opt/demo
WORKDIR /opt/demo
