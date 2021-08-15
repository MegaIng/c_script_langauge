from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, Optional

from c_type import CType


@dataclass(frozen=True)
class CDeclFunction:
    name: str
    header: CHeader
    return_type: CType
    arguments: tuple[tuple[Optional[str], CType], ...]
    varargs: bool


@dataclass(frozen=True)
class CHeader:
    name: str
    know_dll: str = None
    _function_cache: dict[str, CDeclFunction] = field(default_factory=dict, repr=False, init=False, compare=False)

    def get_proc(self, name: str) -> CDeclFunction:
        if name not in self._function_cache:
            self._function_cache[name] = self._get_proc(name)
        return self._function_cache[name]

    def _get_proc(self, name: str) -> CDeclFunction:
        raise ValueError(f"Can't find definition of Function {name!r} in {self.name!r}")


class HeaderFinder(Protocol):
    def get_header(self, name: str) -> Optional[CHeader]:
        pass
