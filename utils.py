from __future__ import annotations

from typing import TypeAlias

JSONData: TypeAlias = dict[str, 'JSONData'] | list['JSONData'] | str | int | float | bool | None
