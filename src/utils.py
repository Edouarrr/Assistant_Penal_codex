import os
import yaml
import logging


def load_config(path='config/config.yaml'):
    """Load YAML configuration from the given path."""
    with open(path, 'r') as f:
        return yaml.safe_load(f) or {}


def configure_logger(log_file='logs/error.log'):
    """Return a logger that writes errors to the specified file."""
    logger = logging.getLogger('assistant_codex')
    logger.setLevel(logging.ERROR)
    os.makedirs(os.path.dirname(log_file), exist_ok=True)
    if not logger.handlers:
        handler = logging.FileHandler(log_file)
        formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        handler.setFormatter(formatter)
        logger.addHandler(handler)
    return logger
