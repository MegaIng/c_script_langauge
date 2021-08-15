from __future__ import annotations

from dataclasses import dataclass, replace
from inspect import signature
from typing import Optional, TYPE_CHECKING

from c_headers import HeaderFinder, CHeader, CDeclFunction
from c_type import c_void, CType, c_int, c_char_p


@dataclass
class StdlibHeaderFinder(HeaderFinder):
    known_headers: dict[str, CHeader]

    def get_header(self, name: str) -> Optional[CHeader]:
        return self.known_headers.get(name)

    def register(self, cls):
        header = self.known_headers[cls.header_name] = CHeader(cls.header_name, "%crt%")
        for n, f in cls.__dict__.items():
            if isinstance(f, CDeclFunction):
                assert f.header is None
                header._function_cache[n] = replace(f, header=header)
        return header


def decl(func):
    arguments = []
    return_type = c_void
    sig = signature(func)
    varargs = False
    for a, param in sig.parameters.items():
        if a.startswith('_'):
            a = None
        if param.kind == param.VAR_POSITIONAL:
            varargs = True
            continue
        t = param.annotation
        if isinstance(t, str):
            t = eval(t)
        assert isinstance(t, CType)
        arguments.append((a, t))
    if sig.return_annotation is not None:
        return_type = sig.return_annotation
        if isinstance(return_type, str):
            return_type = eval(return_type)
        assert isinstance(return_type, CType)
    return CDeclFunction(func.__name__, None, return_type, tuple(arguments), varargs)


stdlib = StdlibHeaderFinder({})


# noinspection PyMethodParameters
@stdlib.register
class StdIO:
    header_name = "stdio.h"

    @decl
    def puts(s: c_char_p) -> c_int: ...

    @decl
    def printf(format: c_char_p, *_) -> c_int: ...
