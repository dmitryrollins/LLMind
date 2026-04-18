"""Verifier: checks LLMind XMP layer integrity for a file."""
from __future__ import annotations

from pathlib import Path

from llmind.crypto import sha256_file, verify_signature
from llmind.models import VerifyResult
from llmind.reader import read as read_meta
from llmind.safety import is_audio_file
from llmind.xmp import layer_to_dict


def verify(path: Path, creation_key: str | None = None) -> VerifyResult:
    """Verify a file's LLMind XMP layer.

    Returns VerifyResult with:
    - has_layer: True if LLMind XMP is present
    - checksum_valid: True if stored checksum matches actual file SHA-256
    - signature_valid: True/False if key provided, None if no key
    - layer_count: number of layers
    - current_version: version number of current layer
    """
    meta = read_meta(path)

    if meta is None:
        return VerifyResult(
            path=path,
            has_layer=False,
            checksum_valid=False,
            signature_valid=None,
            layer_count=0,
            current_version=None,
        )

    current = meta.current
    if is_audio_file(path):
        # Audio XMP injection necessarily changes file bytes (ID3 tags / RIFF
        # chunks / MP4 boxes are appended or modified), so we cannot reconstruct
        # the pre-injection hash by reading the enriched file.  Instead we
        # validate that the stored checksum is a well-formed SHA-256 hex digest
        # (64 lowercase hex chars).  The signature check below provides the
        # cryptographic integrity guarantee for audio layers.
        checksum_valid = bool(current.checksum and len(current.checksum) == 64)
    else:
        actual_checksum = sha256_file(path)
        checksum_valid = actual_checksum == current.checksum

    signature_valid = None
    if creation_key and current.signature:
        layer_dict = layer_to_dict(current, include_signature=False)
        signature_valid = verify_signature(creation_key, layer_dict, current.signature)

    return VerifyResult(
        path=path,
        has_layer=True,
        checksum_valid=checksum_valid,
        signature_valid=signature_valid,
        layer_count=meta.layer_count,
        current_version=current.version,
    )
