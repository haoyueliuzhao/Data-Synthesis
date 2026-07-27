# Migrated Server Recovery

This document records the environment restored on 2026-07-27. It contains no
credentials and is safe to keep in version control.

## Project layout

```text
/data1/zhuxinrui/projects/Data-Synthesis/
  trusted_data_synthesis/       active framework
  raw_financial_data_lake/      read-only finance archive
```

Activate the project from any directory:

```bash
source /data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis/scripts/activate_project.sh
```

The activation script enters the project Python environment and loads the
ignored archive `.env`, including the local database URL and configured API
credentials.

## Verified runtime

- Ubuntu 24.04, x86_64
- Python 3.12.13
- 8 NVIDIA A100-SXM4-80GB GPUs
- NVIDIA driver 570.158.01, CUDA runtime 12.8
- PyTorch 2.7.1+cu128 with CUDA, BF16, and NCCL available
- Transformers 4.52.4, Accelerate 1.7.0, Datasets 3.6.0, PEFT 0.15.2
- PostgreSQL 16.14 on a protected Unix socket

The exact training dependency set is frozen in
`constraints/a100-cu128.txt`. Install PyTorch from the cu128 wheel index before
applying the remaining constraints; the broad package metadata intentionally
remains platform-neutral.

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

The server does not listen on TCP. The restored `finraw` database contains the
current schema and source registry, but no migrated production rows. A dump
from the previous server is still required to restore the latest hot database
builds.

The user service starts at login. Starting it before the user logs in after a
machine reboot requires an administrator to run:

```bash
sudo loginctl enable-linger zhuxinrui
```

## Archive migration

Published archive manifests retain their original `/workspace/Data Synthesis`
storage URIs for provenance. The Finance Adapter maps only that registered
legacy archive root to the new archive root at read time, keeps the archived
URI unchanged, confines the mapped path under the configured archive, and
still verifies object hashes.

## Model cache

The historical v0.8 preflight adapter targets
`Qwen/Qwen2.5-7B-Instruct` revision
`a09a35458c702b33eeacc393d103063234e8bc28`. Its local base-model directory is:

```text
/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28
```

Model shards must match the official SHA-256 values before use. The existing
LoRA adapter is under `artifacts/training_utility_mvp/preflight/model_D2`.

## Remaining external recovery item

No PostgreSQL dump or complete export of the newest production KG build was
present in the migrated filesystem. The older archive-pinned KG remains usable,
but the previous server's latest DB-only facts, KG, and build metadata cannot be
reconstructed from the files currently available.

