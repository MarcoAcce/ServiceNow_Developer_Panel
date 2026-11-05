#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

PYTHON="${PYTHON:-virtual_environment/bin/python}"
source packaging/build_common.sh

build_setup
echo "Built dist/$SETUP_NAME"
