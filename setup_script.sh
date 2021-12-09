#!/bin/bash

export PYTHONPATH="${PYTHONPATH}:/home/mlyniec/Dial-a-Ride/dialRL"
export PYTHONPATH="${PYTHONPATH}:/home/mlyniec/Dial-a-Ride/dialRL/strategies/external/darp_rf"
export GUROBI_HOME="/home/mlyniec/gurobi950/linux64"
export PATH="${PATH}:${GUROBI_HOME}/bin"
export LD_LIBRARY_PATH="${LD_LIBRARY_PATH}:${GUROBI_HOME}/lib"
echo $LD_LIBRARY_PATH