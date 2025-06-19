# Assistant Penal Codex

Assistant Penal Codex is an experimental workflow for digitizing legal documents and making them queryable with modern language models. The project focuses on:

- **Optical Character Recognition (OCR)** of scanned codebooks and PDFs.
- **Vectorizing text** using OpenAI embeddings stored in **ChromaDB** for retrieval.
- **Querying multiple LLMs** to obtain answers from the vector store.
- **Generating documents** from query results to streamline research.
- **Deploying** the complete pipeline on **Railway** for easy management.

## Directory layout

```
├── data/
│   ├── raw/          # original scanned files
│   └── processed/    # text extracted from OCR
├── src/
│   ├── ocr/          # OCR routines
│   ├── vector/       # embedding and ChromaDB code
│   ├── query/        # LLM querying utilities
│   └── generate/     # document generation scripts
├── docs/             # generated reports
└── Dockerfile        # container setup for Railway
```

## Environment variables

- `OPENAI_API_KEY` – token for OpenAI embeddings and LLMs
- `CHROMADB_URL` – location of the ChromaDB instance
- `RAILWAY_TOKEN` – deployment token for Railway
- `PORT` – web service port if running as an API

These variables should be set in your environment or in Railway's configuration panel.


## OCR SharePoint synchronization

To sync the OCR output with SharePoint, run:

```bash
python -m core.ocr_sharepoint_sync
```

On Railway you can schedule this with a cron job:

```yaml
- name: "Synchronisation SharePoint + OCR"
  schedule: "0 2 * * *"
  command: "python -m core.ocr_sharepoint_sync"
```

