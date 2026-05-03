import io
import pytest
from pathlib import Path
from llmind.models import Layer


def _make_minimal_jpeg() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, format="JPEG")
    return buf.getvalue()


def _make_minimal_png() -> bytes:
    from PIL import Image
    buf = io.BytesIO()
    Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, format="PNG")
    return buf.getvalue()


def _make_minimal_pdf() -> bytes:
    import pikepdf
    buf = io.BytesIO()
    with pikepdf.new() as pdf:
        pdf.save(buf)
    return buf.getvalue()


@pytest.fixture
def jpeg_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.jpg"
    path.write_bytes(_make_minimal_jpeg())
    return path


@pytest.fixture
def png_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.png"
    path.write_bytes(_make_minimal_png())
    return path


@pytest.fixture
def pdf_file(tmp_path: Path) -> Path:
    path = tmp_path / "test.pdf"
    path.write_bytes(_make_minimal_pdf())
    return path


@pytest.fixture
def sample_layer() -> Layer:
    return Layer(
        version=1,
        timestamp="2026-04-09T12:00:00Z",
        generator="llmind-cli/0.1.0",
        generator_model="qwen2.5-vl:7b",
        checksum="a" * 64,
        language="en",
        description="A white 1x1 test image with no content.",
        text="Hello world",
        structure={"type": "test", "regions": [], "figures": [], "tables": []},
        key_id="abcdef1234567890",
        signature="sig" * 20,
    )


# Shared XMP fixture used by test_injector, test_reader, and test_cli
SAMPLE_XMP = (
    '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>\n'
    '<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
    '<rdf:RDF xmlns:rdf="http://www.w3.org/1999/02/22-rdf-syntax-ns#">\n'
    '<rdf:Description rdf:about=""\n'
    '  xmlns:llmind="https://llmind.org/ns/1.0/"\n'
    '  llmind:version="1"\n'
    '  llmind:format_version="1.0"\n'
    '  llmind:generator="llmind-cli/0.1.0"\n'
    '  llmind:generator_model="qwen2.5-vl:7b"\n'
    '  llmind:timestamp="2026-04-09T12:00:00Z"\n'
    '  llmind:language="en"\n'
    '  llmind:checksum="' + "a" * 64 + '"\n'
    '  llmind:key_id="abcdef1234567890"\n'
    '  llmind:signature="sig"\n'
    '  llmind:layer_count="1"\n'
    '  llmind:immutable="true"\n'
    '>\n'
    '<llmind:description>Test</llmind:description>\n'
    '<llmind:text>Hello</llmind:text>\n'
    '<llmind:structure>{}</llmind:structure>\n'
    '<llmind:history>[{"version":1,"timestamp":"2026-04-09T12:00:00Z",'
    '"generator":"llmind-cli/0.1.0","generator_model":"qwen2.5-vl:7b",'
    '"checksum":"' + "a" * 64 + '","language":"en","description":"Test",'
    '"text":"Hello","structure":{},"key_id":"abcdef1234567890","signature":"sig"}]'
    '</llmind:history>\n'
    '</rdf:Description>\n'
    '</rdf:RDF>\n'
    '</x:xmpmeta>\n'
    '<?xpacket end="w"?>'
)
