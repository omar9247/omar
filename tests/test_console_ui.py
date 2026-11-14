import hashlib
import shutil
import subprocess
import xml.etree.ElementTree as ET
from html.parser import HTMLParser
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.skipif(shutil.which('node') is None, reason='Node is optional')
def test_console_ui():
    result = subprocess.run(['node', 'tests/test_console_ui.cjs'], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stdout + result.stderr


def test_drift_is_requested_not_automatic():
    class Markup(HTMLParser):
        def __init__(self):
            super().__init__()
            self.nodes = {}

        def handle_starttag(self, tag, attrs):
            attrs = dict(attrs)
            if 'id' in attrs:
                self.nodes[attrs['id']] = (tag, attrs)

    markup = Markup()
    markup.feed((ROOT / 'web/static/index.html').read_text())
    tag, button = markup.nodes['drift-toggle']
    assert tag == 'button' and button['type'] == 'button'
    assert button['aria-expanded'] == 'false' and button['aria-controls'] == 'drift-content'
    assert 'hidden' in markup.nodes['drift-content'][1]


def test_local_web_silhouette():
    original = ROOT / 'web/static/images/human-silhouette.svg'
    assert hashlib.sha256(original.read_bytes()).hexdigest() == '0deff48bf3409b7f3c3c0d42730242f69908d9d80c68d270d1130f7642cda325'
    ns = {'s': 'http://www.w3.org/2000/svg'}
    source = ET.parse(original).getroot()
    source_path = source.find('.//s:path', ns)
    body_file = ROOT / 'web/static/images/body-systems.svg'
    assert '<g ' in body_file.read_text() and '<ns0:g' not in body_file.read_text()
    body = ET.parse(body_file).getroot()
    assert body.attrib['viewBox'] == source.attrib['viewBox'] == '0 0 278.8 984.46'
    whole_body = body.find('.//s:g[@data-lane="bone"]', ns)
    assert whole_body.attrib['transform'] == source.find('s:g', ns).attrib['transform']
    assert whole_body.find('s:path', ns).attrib == source_path.attrib
    parts = [e for e in body.iter() if 'data-lane' in e.attrib]
    assert {e.attrib['data-lane'] for e in parts} == {'neuro', 'immune', 'cardio', 'metab', 'bone', 'habitat'}
    assert all(e.attrib['role'] == 'button' and e.attrib['tabindex'] == '0' for e in parts)
    for e in body.iter():
        assert e.tag.split('}')[-1] not in {'script', 'image', 'foreignObject', 'clipPath', 'mask'}
        assert not any(k.startswith('on') for k in e.attrib)
        assert all(v.startswith('#') for k, v in e.attrib.items() if k.endswith('href'))
