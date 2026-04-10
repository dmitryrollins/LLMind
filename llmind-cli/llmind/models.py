from __future__ import annotations

from dataclasses import dataclass
from typing import NamedTuple
from pathlib import Path


@dataclass(frozen=True)
class ExtractionResult:
    language: str
    description: str
    text: str
    structure: dict  # mutable — do not mutate in place


@dataclass(frozen=True)
class Layer:
    version: int
    timestamp: str          # ISO 8601 UTC
    generator: str          # "llmind-cli/0.1.0"
    generator_model: str
    checksum: str           # SHA-256 hex of original file bytes
    language: str
    description: str
    text: str
    structure: dict         # mutable — do not mutate in place
    key_id: str             # first 16 hex chars of SHA-256(creation_key)
    signature: str | None = None  # HMAC-SHA256; None if unsigned


@dataclass(frozen=True)
class KeyFile:
    key_id: str
    creation_key: str       # 64 hex chars (256-bit)
    created: str            # ISO 8601
    file: str               # original filename
    note: str = "Required to modify or delete layers. Not recoverable."


@dataclass(frozen=True)
class LLMindMeta:
    layers: tuple[Layer, ...]   # full history; index 0 = v1
    current: Layer              # layers[-1]
    layer_count: int
    immutable: bool

    def __post_init__(self) -> None:
        if not self.layers:
            raise ValueError("layers must not be empty")
        if self.layer_count != len(self.layers):
            raise ValueError(
                f"layer_count ({self.layer_count}) != len(layers) ({len(self.layers)})"
            )
        if self.current != self.layers[-1]:
            raise ValueError("current must equal layers[-1]")


class EnrichResult(NamedTuple):
    path: Path
    success: bool
    skipped: bool
    version: int | None
    regions: int
    figures: int
    tables: int
    elapsed: float
    error: str | None


class VerifyResult(NamedTuple):
    path: Path
    has_layer: bool
    checksum_valid: bool
    signature_valid: bool | None   # None if no key provided
    layer_count: int
    current_version: int | None
