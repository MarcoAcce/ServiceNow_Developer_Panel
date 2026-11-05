#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-virtual_environment/Scripts/python.exe}"
source packaging/build_common.sh

build_setup
echo "Built dist/$SETUP_NAME.exe"
