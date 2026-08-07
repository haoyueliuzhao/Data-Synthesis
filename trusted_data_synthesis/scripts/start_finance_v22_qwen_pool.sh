#!/usr/bin/env bash
set -euo pipefail

ROOT=/data1/zhuxinrui/projects/Data-Synthesis/trusted_data_synthesis
MODEL=/data1/zhuxinrui/models/Qwen2.5-7B-Instruct-a09a35458c702b33eeacc393d103063234e8bc28
RUN_DIR=/tmp/qwen_v22_pool
PIDS=()

mkdir -p "$RUN_DIR"

start_server() {
  local gpu="$1"
  local port="$2"
  env CUDA_VISIBLE_DEVICES="$gpu" \
    "$ROOT/.venv/bin/transformers" serve "$MODEL" \
    --host 127.0.0.1 \
    --port "$port" \
    --device cuda:0 \
    --dtype bfloat16 \
    --continuous-batching \
    --cb-max-memory-percent 0.75 \
    --cb-max-batch-tokens 32768 \
    --reasoning off \
    --log-level warning \
    >"$RUN_DIR/server_${port}.log" 2>&1 &
  local pid="$!"
  PIDS+=("$pid")
  echo "$pid" >"$RUN_DIR/server_${port}.pid"
}

cleanup() {
  kill -KILL "${PIDS[@]}" 2>/dev/null || true
}

trap cleanup EXIT INT TERM

start_server 0 8010
start_server 2 8011
start_server 3 8012
start_server 4 8013
start_server 5 8014
start_server 6 8015
start_server 7 8016

wait
