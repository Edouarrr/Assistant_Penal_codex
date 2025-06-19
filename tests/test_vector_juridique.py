import os
import sys
import types
import importlib

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def test_load_settings(tmp_path, monkeypatch):
    yaml_content = """
vectorization:
  persist_directory: mydb
  other: value
"""
    settings_file = tmp_path / "settings.yaml"
    settings_file.write_text(yaml_content, encoding="utf-8")

    # stub heavy dependencies before importing the module
    monkeypatch.setitem(sys.modules, 'openai', types.SimpleNamespace())
    monkeypatch.setitem(sys.modules, 'PyPDF2', types.SimpleNamespace(PdfReader=lambda *a, **k: []))
    monkeypatch.setitem(
        sys.modules,
        'langchain.text_splitter',
        types.SimpleNamespace(RecursiveCharacterTextSplitter=lambda *a, **k: None),
    )
    stub_chromadb = types.ModuleType('chromadb')
    stub_utils = types.ModuleType('chromadb.utils')
    stub_utils.embedding_functions = types.SimpleNamespace(OpenAIEmbeddingFunction=lambda *a, **k: None)
    stub_chromadb.PersistentClient = lambda *a, **k: types.SimpleNamespace(get_or_create_collection=lambda *a, **k: None)
    stub_chromadb.utils = stub_utils
    monkeypatch.setitem(sys.modules, 'chromadb', stub_chromadb)
    monkeypatch.setitem(sys.modules, 'chromadb.utils', stub_utils)

    module = importlib.import_module('core.vector_juridique')
    data = module.VectorJuridique._load_settings(str(settings_file))
    assert data == {"persist_directory": "mydb", "other": "value"}
