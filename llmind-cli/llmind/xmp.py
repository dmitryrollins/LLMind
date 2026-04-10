"""XMP builder and parser for LLMind metadata.

This module is file-system agnostic: it only processes strings.
It imports only from llmind.models and the Python standard library.
"""

from __future__ import annotations

import json
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape as _xml_escape

from llmind.models import Layer, LLMindMeta

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

LLMIND_NS = "https://llmind.org/ns/1.0/"
RDF_NS = "http://www.w3.org/1999/02/22-rdf-syntax-ns#"

XMP_PACKET_BEGIN = '<?xpacket begin="\ufeff" id="W5M0MpCehiHzreSzNTczkc9d"?>'
XMP_PACKET_END = '<?xpacket end="w"?>'

_ESCAPE_TABLE = {'"': "&quot;"}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _escape(text: str) -> str:
    """XML-escape a string, including double quotes."""
    return _xml_escape(text, _ESCAPE_TABLE)


def _ll(name: str) -> str:
    """Return a Clark-notation tag for the llmind namespace."""
    return f"{{{LLMIND_NS}}}{name}"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def layer_to_dict(layer: Layer, include_signature: bool = True) -> dict[str, object]:
    """Convert a Layer to a plain dict suitable for HMAC signing or history JSON.

    Args:
        layer: The layer to convert.
        include_signature: When False the 'signature' key is omitted (use
            this when computing the payload that will be signed).

    Returns:
        A new dict; the original Layer is not mutated.
    """
    d: dict[str, object] = {
        "version": layer.version,
        "timestamp": layer.timestamp,
        "generator": layer.generator,
        "generator_model": layer.generator_model,
        "checksum": layer.checksum,
        "language": layer.language,
        "description": layer.description,
        "text": layer.text,
        "structure": layer.structure,
        "key_id": layer.key_id,
    }
    if include_signature:
        d["signature"] = layer.signature
    return d


def build_xmp(layers: list[Layer]) -> str:
    """Build an XMP XML packet string from one or more layers.

    The last element of *layers* is treated as the current (most recent) layer.
    All previously applied layers are recorded in the ``llmind:history`` element
    so that the full provenance chain is preserved.

    Args:
        layers: Non-empty list of Layer objects in chronological order.

    Returns:
        A UTF-8 XMP string enclosed in xpacket markers.
    """
    if not layers:
        raise ValueError("layers must not be empty")

    current = layers[-1]
    layer_count = len(layers)

    history_json = _escape(
        json.dumps([layer_to_dict(la, include_signature=True) for la in layers],
                   ensure_ascii=False)
    )
    structure_json = _escape(
        json.dumps(current.structure, ensure_ascii=False)
    )

    # Build attribute block (order mirrors the spec for readability)
    attrs = (
        f'    xmlns:llmind="{LLMIND_NS}"\n'
        f'    llmind:version="{current.version}"\n'
        f'    llmind:format_version="1.0"\n'
        f'    llmind:generator="{_escape(current.generator)}"\n'
        f'    llmind:generator_model="{_escape(current.generator_model)}"\n'
        f'    llmind:timestamp="{_escape(current.timestamp)}"\n'
        f'    llmind:language="{_escape(current.language)}"\n'
        f'    llmind:checksum="{_escape(current.checksum)}"\n'
        f'    llmind:key_id="{_escape(current.key_id)}"\n'
        f'    llmind:signature="{_escape(current.signature or "")}"\n'
        f'    llmind:layer_count="{layer_count}"\n'
        f'    llmind:immutable="true"'
    )

    body = (
        f"{XMP_PACKET_BEGIN}\n"
        f'<x:xmpmeta xmlns:x="adobe:ns:meta/">\n'
        f'  <rdf:RDF xmlns:rdf="{RDF_NS}">\n'
        f'    <rdf:Description rdf:about=""\n'
        f"{attrs}\n"
        f"    >\n"
        f"      <llmind:description>{_escape(current.description)}</llmind:description>\n"
        f"      <llmind:text>{_escape(current.text)}</llmind:text>\n"
        f"      <llmind:structure>{structure_json}</llmind:structure>\n"
        f"      <llmind:history>{history_json}</llmind:history>\n"
        f"    </rdf:Description>\n"
        f"  </rdf:RDF>\n"
        f"</x:xmpmeta>\n"
        f"{XMP_PACKET_END}"
    )
    return body


def parse_xmp(xmp_string: str) -> LLMindMeta:
    """Parse an XMP XML string into a LLMindMeta instance.

    Args:
        xmp_string: A valid XMP string produced by :func:`build_xmp`.

    Returns:
        A LLMindMeta with all layers reconstructed from the history element.

    Raises:
        ValueError: If the ``llmind:version`` attribute is not present.
    """
    # Strip xpacket markers before parsing — ET cannot handle PIs at document level
    body = xmp_string
    if body.startswith("<?xpacket"):
        body = body[body.index("?>") + 2:]
    if body.rstrip().endswith("?>"):
        body = body[: body.rindex("<?")]

    root = ET.fromstring(body.strip())

    # Locate rdf:Description — walk regardless of prefix mapping
    rdf_desc = None
    for elem in root.iter():
        if elem.tag == f"{{{RDF_NS}}}Description":
            rdf_desc = elem
            break

    if rdf_desc is None:
        raise ValueError("No rdf:Description element found in XMP")

    # Validate presence of llmind:version
    if _ll("version") not in rdf_desc.attrib:
        raise ValueError("llmind:version attribute is missing from rdf:Description")

    # Retrieve history child element
    history_elem = rdf_desc.find(_ll("history"))
    if history_elem is None or history_elem.text is None:
        raise ValueError("llmind:history element is missing or empty")

    try:
        history_data: list[dict[str, object]] = json.loads(history_elem.text)
        layers: list[Layer] = [
            Layer(
                version=int(d["version"]),
                timestamp=str(d["timestamp"]),
                generator=str(d["generator"]),
                generator_model=str(d["generator_model"]),
                checksum=str(d["checksum"]),
                language=str(d["language"]),
                description=str(d["description"]),
                text=str(d["text"]),
                structure=dict(d.get("structure") or {}),
                key_id=str(d["key_id"]),
                signature=d.get("signature"),
            )
            for d in history_data
        ]
    except (json.JSONDecodeError, KeyError, TypeError) as exc:
        raise ValueError(f"Malformed llmind:history in XMP: {exc}") from exc

    return LLMindMeta(
        layers=tuple(layers),
        current=layers[-1],
        layer_count=len(layers),
        immutable=True,
    )
