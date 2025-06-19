import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import configure_logger


def test_error_logging(tmp_path):
    log_file = tmp_path / 'error.log'
    logger = configure_logger(str(log_file))
    logger.error('failure')
    logger.handlers[0].flush()
    with open(log_file) as f:
        data = f.read()
    assert 'failure' in data
