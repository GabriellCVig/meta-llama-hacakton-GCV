echo "Start the primary model (llama3.3:70b) on port 11411"
ollama serve llama3.3:70b-instruct-q8_0

echo "Start the API server on port 8000"
uv run -- uvicorn api:app --host 0.0.0.0