#!/usr/bin/env bash

# Source this file from any directory:
#   source trusted_data_synthesis/scripts/activate_project.sh

if [[ "${BASH_SOURCE[0]}" == "$0" ]]; then
    echo "This script must be sourced, not executed." >&2
    exit 2
fi

ACTIVE_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PROJECT_ROOT="$(cd "${ACTIVE_ROOT}/.." && pwd)"
ARCHIVE_ROOT="${PROJECT_ROOT}/raw_financial_data_lake"
VENV_ROOT="${ACTIVE_ROOT}/.venv"
STORAGE_ROOT="${DATA_SYNTHESIS_STORAGE_ROOT:-$(cd "${PROJECT_ROOT}/../.." && pwd)}"
POSTGRES_ROOT="${STORAGE_ROOT}/services/data-synthesis-postgres"

if [[ -f "${VENV_ROOT}/bin/activate" ]]; then
    # shellcheck disable=SC1091
    source "${VENV_ROOT}/bin/activate"
elif [[ -x "${VENV_ROOT}/bin/python" ]]; then
    # A migrated Conda prefix does not include a virtualenv activation script.
    export VIRTUAL_ENV="${VENV_ROOT}"
    export PATH="${VENV_ROOT}/bin:${PATH}"
    hash -r
else
    echo "Missing Python environment: ${VENV_ROOT}" >&2
    return 1
fi

if [[ -x "${POSTGRES_ROOT}/env/bin/psql" ]]; then
    export PATH="${PATH}:${POSTGRES_ROOT}/env/bin"
fi

if [[ -f "${ARCHIVE_ROOT}/.env" ]]; then
    set -o allexport
    # shellcheck disable=SC1091
    source "${ARCHIVE_ROOT}/.env"
    set +o allexport
fi

export DATA_SYNTHESIS_PROJECT_ROOT="${PROJECT_ROOT}"
export DATA_SYNTHESIS_ACTIVE_ROOT="${ACTIVE_ROOT}"
export DATA_SYNTHESIS_ARCHIVE_ROOT="${ARCHIVE_ROOT}"
export DATA_SYNTHESIS_STORAGE_ROOT="${STORAGE_ROOT}"
export DATA_SYNTHESIS_MODEL_ROOT="${DATA_SYNTHESIS_MODEL_ROOT:-${STORAGE_ROOT}/models}"
export HF_HOME="${HF_HOME:-${STORAGE_ROOT}/cache/huggingface}"
export PYTHONUNBUFFERED=1
export TOKENIZERS_PARALLELISM=false

echo "Data Synthesis environment active"
echo "  project: ${PROJECT_ROOT}"
echo "  python:  $(command -v python)"
