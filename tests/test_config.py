import os
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.utils import load_config


def test_load_config():
    config = load_config('config/config.yaml')
    assert isinstance(config, dict)
    assert config.get('ocr', {}).get('language') == 'eng'
