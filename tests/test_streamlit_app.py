import importlib
import runpy
import pytest

st = pytest.importorskip('streamlit')
app = pytest.importorskip('streamlit_app')

def test_tabs_and_command_palette(monkeypatch):
    called = {'tabs': 0, 'palette': 0}

    def fake_tabs(*args, **kwargs):
        called['tabs'] += 1
        class Dummy:
            def __enter__(self):
                return self
            def __exit__(self, exc_type, exc, tb):
                pass
        return [Dummy()]

    def fake_palette(*args, **kwargs):
        called['palette'] += 1

    monkeypatch.setattr(st, 'tabs', fake_tabs, raising=False)
    if hasattr(st, 'command_palette'):
        monkeypatch.setattr(st, 'command_palette', fake_palette, raising=False)

    if hasattr(app, 'main'):
        app.main()
    else:
        importlib.reload(app)

    assert called['tabs'] > 0
    if hasattr(st, 'command_palette'):
        assert called['palette'] > 0
