from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RenderedStep:
    """Stepik-ready learner step after verified rendering.

    This is a transport model only. It contains no lesson-specific compilation logic.
    """

    position: int
    block_name: str
    text: str
    source: dict[str, Any]
    source_git_paths: tuple[str, ...]

    def block(self) -> dict[str, Any]:
        return {
            "name": self.block_name,
            "text": self.text,
            "source": dict(self.source),
        }
