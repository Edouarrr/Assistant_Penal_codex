# Assistant Penal Codex

Assistant Penal Codex is an experimental workflow for digitizing legal documents and making them queryable with modern language models. The project focuses on:

- **Optical Character Recognition (OCR)** of scanned codebooks and PDFs.
- **SharePoint synchronization** via Microsoft Graph with automatic OCR.
- **Vectorizing text** using OpenAI embeddings stored in **ChromaDB** for retrieval.
- **Querying multiple LLMs** to obtain answers from the vector store.
- **Generating documents** from query results to streamline research.
- **Deploying** the complete pipeline on **Railway** for easy management.

## Directory layout

```
├── chroma_db/           # local ChromaDB embeddings storage
├── config/              # YAML configs and prompt files
├── core/                # core processing modules and sync helpers
├── logs/                # runtime logs
├── ocr_output/          # text extracted from OCR
├── raw_documents/       # source scanned files and PDFs
├── src/                 # shared helper utilities
├── static/              # static assets for the web app
├── summaries/           # generated summaries
├── templates/           # document templates
├── tests/               # unit tests suite
├── ui/                  # Streamlit UI components
├── ocr_sharepoint_sync.py  # SharePoint sync helper (legacy)
├── streamlit_app.py     # main web application interface
└── requirements.txt     # Python dependencies
```

## Environment variables

Set the following variables in your environment or in Railway's configuration panel.

### OpenAI

- `OPENAI_API_KEY` – token for OpenAI embeddings and LLMs

### SharePoint

- `MS_TENANT_ID` – Microsoft Azure tenant ID
- `MS_CLIENT_ID` – application client ID
- `MS_CLIENT_SECRET` – client secret associated with the app
- `SHAREPOINT_SITE_ID` – identifier of the SharePoint site
- `SHAREPOINT_DOC_LIB` – document library or drive ID

Other useful variables:

- `CHROMADB_URL` – location of the ChromaDB instance
- `RAILWAY_TOKEN` – deployment token for Railway
- `PORT` – web service port if running as an API


## OCR SharePoint synchronization

The synchronization logic lives in ``core/ocr_sharepoint_sync.py``. To sync the
OCR output with SharePoint, run:

```bash
python -m core.ocr_sharepoint_sync
```

On Railway you can schedule this with a cron job:

```yaml
- name: "Synchronisation SharePoint + OCR"
  schedule: "0 2 * * *"
  command: "python -m core.ocr_sharepoint_sync"
```

## Running the pipeline

The following steps show how to process documents from OCR to vector embeddings.

1. **Synchronize SharePoint and run OCR**

   ```bash
   python -m core.ocr_sharepoint_sync
   ```

   New or updated files are saved under `raw_documents/` and OCR text is written
   to `ocr_output/`.

2. **Generate summaries**

   Use the `PieceSynthesizer` class to create JSON summaries for each text file
   in `ocr_output/`:

   ```python
   from pathlib import Path
   from core.piece_synthesizer import PieceSynthesizer

   synth = PieceSynthesizer()
   for txt_file in Path("ocr_output").rglob("*.txt"):
       text = txt_file.read_text(encoding="utf-8")
       summary = synth.create_summary(
           text,
           metadata={},
           parties_citees=[],
           faits_essentiels="",
           incoherences_detectees="",
           sourcing={"fichier_source": txt_file.name},
       )
       synth.save_summary(summary, txt_file.name)
   ```

3. **Build an entity map**

   ```python
   from core.memory_warming import load_all_summaries, build_entity_map, save_entity_map

   summaries = load_all_summaries("summaries")
   entity_map = build_entity_map(summaries)
   save_entity_map(entity_map, dossier="dossier1")
   ```

4. **Vectorize PDFs**

   ```bash
   python -m core.vector_juridique
   ```

   This reads PDFs from `ocr_output/`, stores embeddings in ChromaDB and writes
   page summaries to `summaries/`.

## Scheduled jobs

Railway can run several maintenance scripts on a schedule. Below is an example
configuration illustrating the three main cron jobs used by the project:

```yaml
- name: "Vectorisation OCR"
  schedule: "0 3 * * *"
  command: "python ocr_vector_sync.py"

- name: "Veille juridique AI"
  schedule: "30 4 * * *"
  command: "python veille_juridique_ai.py"

- name: "Backup ChromaDB"
  schedule: "0 5 * * *"
  command: "python backup_chroma.py"
```

These jobs run automatically to maintain the system:
- **Vectorisation OCR** (3:00 AM): Processes new OCR text into vector embeddings
- **Veille juridique AI** (4:30 AM): Performs automated legal monitoring
- **Backup ChromaDB** (5:00 AM): Creates backups of the vector database