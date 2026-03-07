#!/bin/bash
pkill -f "uvicorn app.main:app"
pip install -r requirements.txt
export PYTHONPATH=$PYTHONPATH:.
PORT="${PORT:-5001}"
UVICORN_RELOAD="${UVICORN_RELOAD:-0}"
UVICORN_WORKERS="${UVICORN_WORKERS:-2}"
if [ "$UVICORN_RELOAD" = "1" ]; then
  uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --reload
else
  uvicorn app.main:app --host 0.0.0.0 --port "$PORT" --workers "$UVICORN_WORKERS"
fi
