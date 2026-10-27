#!/bin/sh
set -eu

PYTHON="${PYTHON:-python3}"
"$PYTHON" -m unittest discover -s tests -v
