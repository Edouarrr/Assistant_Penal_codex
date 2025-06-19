import os
import logging
from pathlib import Path
from typing import Any


LOG_FILE = Path('logs/access.log')
LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
_logger = logging.getLogger('security')
if not _logger.handlers:
    handler = logging.FileHandler(LOG_FILE)
    formatter = logging.Formatter('[%(asctime)s] %(message)s')
    handler.setFormatter(formatter)
    _logger.addHandler(handler)
_logger.setLevel(logging.INFO)


def chiffrer_fichier(path: str) -> str:
    """Encrypt ``path`` and return the encrypted file path."""
    key = os.getenv('SECURITY_KEY', 'defaultkey')
    data: bytes
    with open(path, 'rb') as f:
        data = f.read()
    encrypted = bytes(b ^ ord(key[i % len(key)]) for i, b in enumerate(data))
    enc_path = f"{path}.enc"
    with open(enc_path, 'wb') as f:
        f.write(encrypted)
    return enc_path


def log_acces(user_id: str, action: str) -> None:
    """Write an access entry to ``logs/access.log``."""
    _logger.info(f"user={user_id} | action={action}")


def verifier_mode_confidentiel() -> bool:
    """Return True if MODE_PRIVILEGE environment variable is truthy."""
    return os.getenv('MODE_PRIVILEGE', 'False').lower() == 'true'


def nettoyer_historique() -> None:
    """Delete log files to clean up history."""
    for path in LOG_FILE.parent.glob('*.log'):
        try:
            path.write_text('')
        except Exception:
            pass
