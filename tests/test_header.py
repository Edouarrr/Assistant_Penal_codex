import pytest

header = pytest.importorskip('ui.components.header')

def test_render_header_contains_header_tag():
    html = header.render_header()
    assert isinstance(html, str)
    assert '<header' in html.lower()
    assert '</header>' in html.lower()
