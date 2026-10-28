#!/usr/bin/env bash
# scripts/smoke_test.sh - End-to-end smoke test for clean installs
set -e

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_ROOT"

PORT="${PORT:-8000}"
HOST="127.0.0.1"
BASE_URL="http://${HOST}:${PORT}"
DB_PATH="output/apophenic.db"
LOG_PATH="output/smoke_server.log"

mkdir -p output

echo "=== Starting Apophenic Memory Smoke Test ==="

# 1. Start the FastAPI server in the background
echo "[1/6] Starting FastAPI server on ${BASE_URL}..."
if [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/bin/uvicorn" ]; then
    UVICORN_CMD="$VIRTUAL_ENV/bin/uvicorn"
elif [ -n "$VIRTUAL_ENV" ] && [ -f "$VIRTUAL_ENV/Scripts/uvicorn.exe" ]; then
    UVICORN_CMD="$VIRTUAL_ENV/Scripts/uvicorn.exe"
elif [ -f ".venv/bin/uvicorn" ]; then
    UVICORN_CMD=".venv/bin/uvicorn"
elif [ -f ".venv/Scripts/uvicorn.exe" ]; then
    UVICORN_CMD=".venv/Scripts/uvicorn.exe"
elif [ -f "../.venv/bin/uvicorn" ]; then
    UVICORN_CMD="../.venv/bin/uvicorn"
elif [ -f "../.venv/Scripts/uvicorn.exe" ]; then
    UVICORN_CMD="../.venv/Scripts/uvicorn.exe"
elif command -v uvicorn >/dev/null 2>&1; then
    UVICORN_CMD="uvicorn"
else
    UVICORN_CMD="python -m uvicorn"
fi

$UVICORN_CMD apophenic_memory.api.main:app --host "$HOST" --port "$PORT" > "$LOG_PATH" 2>&1 &
SERVER_PID=$!

cleanup() {
    echo "Stopping FastAPI server (PID: ${SERVER_PID})..."
    kill "$SERVER_PID" 2>/dev/null || true
    wait "$SERVER_PID" 2>/dev/null || true
    rm -f "$LOG_PATH"
}
trap cleanup EXIT

# Wait for server to become responsive
echo "Waiting for server to become ready..."
SERVER_READY=false
for i in {1..30}; do
    if curl -s -f -o /dev/null "${BASE_URL}/timeline"; then
        SERVER_READY=true
        echo "Server is ready!"
        break
    fi
    sleep 1
done

if [ "$SERVER_READY" != "true" ]; then
    echo "ERROR: Server failed to start or respond within 30 seconds."
    if [ -f "$LOG_PATH" ]; then
        echo "Server Log:"
        cat "$LOG_PATH"
    fi
    exit 1
fi

# 2. Hit GET /timeline and assert 200
echo "[2/6] Testing GET /timeline..."
STATUS_TIMELINE=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/timeline")
if [ "$STATUS_TIMELINE" -ne 200 ]; then
    echo "ERROR: GET /timeline returned HTTP ${STATUS_TIMELINE}, expected 200"
    exit 1
fi
echo "GET /timeline returned 200 OK."

# 3. Hit POST /memories/generate and assert 200
echo "[3/6] Testing POST /memories/generate..."
STATUS_GEN=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${BASE_URL}/memories/generate" \
    -H "Content-Type: application/json" \
    -d '{"gap_start": "2012-03-02", "gap_end": "2012-03-26"}')

if [ "$STATUS_GEN" -ne 200 ]; then
    echo "ERROR: POST /memories/generate returned HTTP ${STATUS_GEN}, expected 200"
    exit 1
fi
echo "POST /memories/generate returned 200 OK."

# 4. Check that output/apophenic.db exists on disk
echo "[4/6] Checking that ${DB_PATH} exists on disk..."
if [ ! -f "$DB_PATH" ]; then
    echo "ERROR: ${DB_PATH} does not exist on disk after generation!"
    exit 1
fi
echo "${DB_PATH} confirmed on disk."

# 5. Hit POST /data/wipe with {"confirm": true}
echo "[5/6] Testing POST /data/wipe..."
STATUS_WIPE=$(curl -s -o /dev/null -w "%{http_code}" \
    -X POST "${BASE_URL}/data/wipe" \
    -H "Content-Type: application/json" \
    -d '{"confirm": true}')

if [ "$STATUS_WIPE" -ne 200 ]; then
    echo "ERROR: POST /data/wipe returned HTTP ${STATUS_WIPE}, expected 200"
    exit 1
fi
echo "POST /data/wipe returned 200 OK."

# 6. Assert that output/apophenic.db no longer exists on disk
echo "[6/6] Verifying that ${DB_PATH} no longer exists on disk..."
if [ -f "$DB_PATH" ]; then
    echo "ERROR: ${DB_PATH} still exists on disk after wipe!"
    exit 1
fi
echo "${DB_PATH} confirmed deleted."

echo "=== All Smoke Tests Passed Successfully! ==="
