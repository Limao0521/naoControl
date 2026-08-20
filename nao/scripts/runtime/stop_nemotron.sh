#!/bin/sh
set -eu

PID_DIR="/home/nao/run/naoControl"
if [ ! -d "$PID_DIR" ]; then
    exit 0
fi

for pid_file in "$PID_DIR"/*.pid; do
    [ -f "$pid_file" ] || continue
    pid=$(cat "$pid_file")
    if kill -0 "$pid" 2>/dev/null; then
        kill "$pid"
    fi
    rm -f "$pid_file"
done
