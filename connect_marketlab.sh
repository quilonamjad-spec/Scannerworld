#!/bin/bash

VM="opc@80.225.199.209"
REMOTE_PORT="8765"
LOCAL_PORT="18766"
DB_URL="http://127.0.0.1:${LOCAL_PORT}"

echo "=== Market Lab VM Connection ==="

echo "[1/4] Checking VM DB service..."

ssh "$VM" "
  if curl -fsS --max-time 3 http://127.0.0.1:${REMOTE_PORT}/health >/dev/null 2>&1; then
    echo 'DB service already running.'
  else
    echo 'DB service not running - starting it...'
    nohup python3 /home/opc/marketlab/service/db_service.py \
      >/tmp/marketlab_db_service.log 2>&1 &
    sleep 2
  fi
"

echo "[2/4] Checking existing SSH tunnel..."

if curl -fsS --max-time 2 "$DB_URL/health" >/dev/null 2>&1; then
    echo "SSH tunnel already working."
else
    echo "[3/4] Starting SSH tunnel..."

    ssh -4 -N \
      -o ExitOnForwardFailure=yes \
      -L ${LOCAL_PORT}:127.0.0.1:${REMOTE_PORT} \
      "$VM" >/tmp/marketlab_ssh_tunnel.log 2>&1 &

    TUNNEL_PID=$!
    echo "$TUNNEL_PID" > ~/.marketlab_tunnel.pid

    sleep 2
fi

echo "[4/4] Testing connection..."

if curl -fsS --max-time 5 "$DB_URL/health" >/dev/null 2>&1; then
    export MARKETLAB_DB_URL="$DB_URL"

    echo
    echo "================================"
    echo "       VM DB READY"
    echo "================================"
    echo "Database: $DB_URL"
    echo "VM:       $VM"
    echo
    echo "MARKETLAB_DB_URL has been set."
else
    echo
    echo "ERROR: VM DB connection failed."
    echo
    echo "Check:"
    echo "  /tmp/marketlab_db_service.log"
    echo "  /tmp/marketlab_ssh_tunnel.log"
fi
