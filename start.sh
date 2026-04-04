#!/bin/bash
# Start Phoenix in the background
uv run DocGen-RAG/launch_phoenix.py &

# Start the FastAPI server in the foreground
uv run uvicorn src.main:app --host 0.0.0.0 --port 8000