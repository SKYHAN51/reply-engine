#!/bin/bash
set -e
echo "Starting ingestion..."
python tools/ingest_documents.py
echo "Starting API server..."
cd demo/api && uvicorn main:app --host 0.0.0.0 --port 8000
