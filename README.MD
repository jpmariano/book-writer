pip install pipreqs
pipreqs .  

export OLLAMA_MAX_LOADED_MODELS=3
export OLLAMA_NUM_PARALLEL=2
ollama serve

ollama pull llama3
ollama pull mistral
ollama pull phi3


Method A: Using Independent TerminalsOpen three separate terminal windows. Run one unique command in each window:Terminal 1: ollama run llama3Terminal 2: ollama run mistralTerminal 3: ollama run phi3

# Request to Model 1
curl http://localhost:11434/api/generate -d '{"model": "llama3", "prompt": "Why is the sky blue?"}'

# Request to Model 2
curl http://localhost:11434/api/generate -d '{"model": "mistral", "prompt": "Write a poem about rain."}'
