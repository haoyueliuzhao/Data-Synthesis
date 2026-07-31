# Migrated Server Recovery

This document records the environment restored on 2026-07-27. It contains no credentials and is
safe to keep in version control.

## Project Layout

```text
/data1/zhuxinrui/projects/Data-Synthesis/
  trusted_data_synthesis/       active framework and VTDO experiment
  raw_financial_data_lake/      read-only Finance archive
```

Activate the project from any directory:

```bash
source /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/scripts/activate_project.sh
```

The activation script enters the project Python environment and may load the ignored archive
`.env`, including the local database URL and configured API credentials. Credentials must not be
copied into tracked configuration, logs, prompts, manifests, or reports.

## Verified Runtime

- Ubuntu 24.04, x86_64
- Python 3.12.13
- 8 NVIDIA A100-SXM4-80GB GPUs
- NVIDIA driver 570.158.01, CUDA runtime 12.8
- PyTorch 2.7.1+cu128 with CUDA, BF16, and NCCL available
- Transformers, Accelerate, Datasets, and PEFT installed in the project environment
- PostgreSQL 16.14 on a protected Unix socket

The exact training dependency set is frozen in `constraints/a100-cu128.txt`. Install PyTorch from
the cu128 wheel index before applying the remaining constraints; broad package metadata remains
platform-neutral.

## PostgreSQL

The project-local service is managed by the user systemd instance:

```bash
systemctl --user status data-synthesis-postgres.service
systemctl --user restart data-synthesis-postgres.service
```

Runtime files are outside Git:

```text
/data1/zhuxinrui/services/data-synthesis-postgres/
  env/     PostgreSQL binaries
  data/    database cluster
  run/     Unix socket
  log/     server log
```

The server does not listen on TCP. The restored `finraw` database contains the current schema and
source registry, but no migrated production rows. A dump from the previous server is still needed
to restore DB-only builds that are absent from the immutable archive.

The user service starts at login. Starting it before the user logs in after a machine reboot
requires an administrator to run:

```bash
sudo loginctl enable-linger zhuxinrui
```

## Archive Migration

Published archive manifests retain their original `/workspace/Data Synthesis` storage URIs for
provenance. The Finance Adapter maps only that registered legacy root to the migrated archive root
at read time, preserves the archived URI, confines the mapped path under the configured archive,
and verifies object hashes.

The deprecated v0.8/v0.9 experiment implementations and generated outputs were permanently
deleted. This is separate from the read-only Finance archive described above, which remains an
active data dependency.

## Student Model Cache

The canonical VTDO student configuration targets `Qwen/Qwen2.5-7B-Instruct` at revision
`a09a35458c702b33eeacc393d103063234e8bc28`. The local base-model directory is:

```text
/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28
```

Model shards must match their frozen SHA-256 values before use. Historical v0.8/v0.9 adapters and
checkpoints were deleted and are not accepted by the current B1-B5 preflight.

## Recovery Verification

```bash
cd /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis
source scripts/activate_project.sh
trusted-synthesis --help
trusted-synthesis audit-generalization --source-root src
pytest -q
ruff check src tests
mypy src
```

The canonical experiment command is:

```bash
trusted-synthesis run-vtdo-experiment \
  --vtdo-config config/vtdo_experiment_finance.json
```

## Remaining External Recovery Item

No PostgreSQL dump or complete export of the newest production KG build was present in the
migrated filesystem. The older archive-pinned KG remains usable, but the previous server's latest
DB-only facts, KG, and build metadata cannot be reconstructed from the files currently available.
