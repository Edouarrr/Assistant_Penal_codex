import logging
from pathlib import Path

# Determine log file location relative to project root
LOG_FILE = Path(__file__).resolve().parent / 'logs' / 'ocr_errors.log'
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[logging.FileHandler(LOG_FILE), logging.StreamHandler()]
)

def sync_documents():
    """Placeholder for OCR SharePoint sync logic."""
    logging.info("Starting SharePoint OCR sync")
    try:
        # TODO: Implement actual sync logic
        pass
    except Exception:
        logging.exception("Error during SharePoint OCR sync")
        raise
    else:
        logging.info("SharePoint OCR sync completed")


if __name__ == '__main__':
    sync_documents()
