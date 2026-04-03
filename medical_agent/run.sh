#!/bin/bash

# Start FastAPI server in the background
echo "Starting FastAPI backend..."
uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload &
FASTAPI_PID=$!

# Start Streamlit frontend
echo "Starting Streamlit Admin frontend..."
streamlit run frontend/admin_app.py --server.port 8501 &
STREAMLIT_ADMIN_PID=$!

# Start Streamlit Client frontend
echo "Starting Streamlit Patient Client frontend..."
streamlit run frontend/client_app.py --server.port 8502 &
STREAMLIT_CLIENT_PID=$!

echo "Systems are up and running!"
echo "Backend: http://localhost:8000/docs"
echo "Admin UI: http://localhost:8501"
echo "Patient Client UI: http://localhost:8502"

# Wait for background processes
trap 'kill $FASTAPI_PID $STREAMLIT_ADMIN_PID $STREAMLIT_CLIENT_PID; exit' SIGINT SIGTERM
wait
