#!/bin/sh
set -eu

BASE="/home/nao/naoControl"
RUNTIME="$BASE/nao/scripts/runtime"
LOG_DIR="/home/nao/logs/naoControl"
PID_DIR="/home/nao/run/naoControl"

mkdir -p "$LOG_DIR" "$PID_DIR"
export PYTHONPATH="/opt/aldebaran/lib/python2.7/site-packages:/home/nao/SimpleWebSocketServer-0.1.2:$RUNTIME/control_server:$RUNTIME/intelligence"
export NAO_CONTROL_HOME="$BASE"

start_service() {
    name="$1"
    shift
    pid_file="$PID_DIR/$name.pid"
    if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "$name already running"
        return
    fi
    "$@" >"$LOG_DIR/$name.log" 2>&1 &
    echo $! >"$pid_file"
    echo "$name started: $(cat "$pid_file")"
}

start_service control python "$RUNTIME/control_server/server.py"
start_service camera python "$RUNTIME/control_server/video_stream.py" \
    --nao_ip 127.0.0.1 --server_ip 169.254.151.5 --server_port 6666 \
    --http_port 8080 --fps 5 --resolution 1
start_service intelligence python "$RUNTIME/intelligence/gateway_server.py"

sleep 3
for pid_file in "$PID_DIR"/*.pid; do
    name=$(basename "$pid_file" .pid)
    if kill -0 "$(cat "$pid_file")" 2>/dev/null; then
        echo "$name=RUNNING"
    else
        echo "$name=FAILED"
        tail -30 "$LOG_DIR/$name.log"
        exit 1
    fi
done
