# Assistant Penal Codex

This project provides a basic environment for OCR and LLM powered processing via Streamlit.

## Development

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the app locally:
```bash
streamlit run app.py
```

## Docker

Build the container and run Streamlit on port 8501:
```bash
docker build -t penal-codex .
docker run -p 8501:8501 penal-codex
```

Environment variables like `OPENAI_API_KEY` and the volume path for ChromaDB can be configured through `railway.json` or passed at runtime.
