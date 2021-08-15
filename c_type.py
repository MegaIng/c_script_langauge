from __future__ import annotations

import ctypes
from abc import abstractmethod, ABC
from dataclasses import dataclass
from functools import cache, reduce
from itertools import product
from operator import mul
from typing import Optional

from frozendict import frozendict

from utils import JSONData

class JSON_KEYS:
    DECLS = "d"
    POINTER = "p"
    BASE = "b"
    VARARGS = "va"
    FUNC = "f"
    ARRAY = "a"
    ARGS = "as"
    ENUM = "e"
    TYPE = "t"
    NAME = "n"
    VALUE = "v"

    STRUCT = "s"
    OPAQUE_STRUCT = "os"
    UNION = "u"
    OPAQUE_UNION = "ou"


@dataclass(frozen=True)
class CType(ABC):
    @abstractmethod
    def to_json(self) -> JSONData:
        raise NotImplementedError


@dataclass(frozen=True)
class CVoid(CType):
    def to_json(self) -> JSONData:
        return "void"


c_void = CVoid()


@dataclass(frozen=True)
class CSpecialType(CType):
    name: str

    def __post_init__(self):
        _special_by_name[self.name] = self

    def to_json(self) -> JSONData:
        return self.name


_special_by_name: dict[str, CSpecialType] = {"void": c_void}

va_list = CSpecialType("va_list")


@dataclass(frozen=True)
class CIntegral(CSpecialType):
    unsigned: bool = None

    def __post_init__(self):
        _special_by_name[self.full_name] = self

    @property
    def full_name(self):
        if self.unsigned is None:
            return self.name
        elif not self.unsigned:
            return f"signed {self.name}"
        else:
            return f"unsigned {self.name}"

    def to_json(self) -> JSONData:
        return self.full_name
    
    @property
    def ctypes(self):
        return getattr(ctypes, "c_"+self.name)


@dataclass(frozen=True)
class CFloatingPoint(CSpecialType):
    pass


@dataclass(frozen=True)
class COpaqueStruct(CType):
    name: str

    def to_json(self) -> JSONData:
        return {JSON_KEYS.TYPE: JSON_KEYS.OPAQUE_STRUCT, JSON_KEYS.NAME: self.name}


@dataclass(frozen=True)
class CStruct(CType):
    name: Optional[str]
    decls: tuple[tuple[Optional[str], CType], ...]

    def to_json(self) -> JSONData:
        return {
            JSON_KEYS.TYPE: JSON_KEYS.STRUCT,
            JSON_KEYS.NAME: self.name,
            JSON_KEYS.DECLS: [{JSON_KEYS.NAME: n, JSON_KEYS.TYPE: t.to_json()} for n, t in self.decls]
        }


@dataclass(frozen=True)
class COpaqueUnion(CType):
    name: str

    def to_json(self) -> JSONData:
        return {JSON_KEYS.TYPE: JSON_KEYS.OPAQUE_UNION, JSON_KEYS.NAME: self.name}


@dataclass(frozen=True)
class CUnion(CType):
    name: Optional[str]
    decls: tuple[tuple[Optional[str], CType], ...]

    def to_json(self) -> JSONData:
        return {
            JSON_KEYS.TYPE: JSON_KEYS.UNION,
            JSON_KEYS.NAME: self.name,
            JSON_KEYS.DECLS: [{JSON_KEYS.NAME: n, JSON_KEYS.TYPE: t.to_json()} for n, t in self.decls]
        }


@dataclass(frozen=True)
class CArray(CType):
    base: CType
    dim: Optional[int]

    def to_json(self) -> JSONData:
        return {
            JSON_KEYS.TYPE: JSON_KEYS.ARRAY,
            JSON_KEYS.BASE: self.base.to_json(),
            JSON_KEYS.VALUE: self.dim
        }


@dataclass(frozen=True)
class CEnum(CType):
    name: str
    values: frozendict[str, int]

    def to_json(self) -> JSONData:
        return {
            JSON_KEYS.TYPE: JSON_KEYS.ENUM,
            JSON_KEYS.NAME: self.name,
            JSON_KEYS.VALUE: dict(self.values)
        }


@dataclass(frozen=True)
class CFunc(CType):
    args: tuple[tuple[Optional[str], CType], ...]
    return_type: CType
    varargs: bool

    def to_json(self) -> JSONData:
        return {
            JSON_KEYS.TYPE: JSON_KEYS.FUNC,
            JSON_KEYS.VARARGS: self.varargs,
            JSON_KEYS.ARGS: [{JSON_KEYS.NAME: n, JSON_KEYS.TYPE: t.to_json()} for n, t in self.args],
            JSON_KEYS.VALUE: self.return_type.to_json(),
        }


@dataclass(frozen=True)
class CPointer(CType):
    base: CType

    def to_json(self) -> JSONData:
        return {
            JSON_KEYS.TYPE: JSON_KEYS.POINTER,
            JSON_KEYS.BASE: self.base.to_json()
        }


c_schar = CIntegral("char", False)
c_uchar = CIntegral("char", True)

c_sshort = CIntegral("short", False)
c_ushort = CIntegral("short", True)

c_sint = CIntegral("int", False)
c_uint = CIntegral("int", True)

c_slong = CIntegral("long", False)
c_ulong = CIntegral("long", True)

c_slong_long = CIntegral("long long", False)
c_ulong_long = CIntegral("long long", True)

c_float = CFloatingPoint("float")
c_double = CFloatingPoint("double")
c_long_double = CFloatingPoint("long double")

c_void_p = CPointer(c_void)

c_char_p = CPointer(c_uchar)


def get_from_names(names) -> CType:
    match names:
        case ["__builtin_va_list"]:
            return va_list
        case ["void"]:
            return c_void
        case ["float"]:
            return c_float
        case ["double"]:
            return c_double
        case ["long", "double"]:
            return c_long_double
        case ["signed", "char"] | ["char"]:
            return c_schar
        case ["unsigned", "char"]:
            return c_uchar
        case ["signed", "short"] | ["short"] | ["signed", "short", "int"] | ["short", "int"]:
            return c_sshort
        case ["unsigned", "short"] | ["unsigned", "short", "int"]:
            return c_ushort
        case ["signed", "int"] | ["int"]:
            return c_sint
        case ["unsigned", "int"] | ["unsigned"]:
            return c_uint
        case ["signed", "long"] | ["long"] | ["signed", "long", "int"] | ["long", "int"]:
            return c_slong
        case ["unsigned", "long"] | ["unsigned", "long", "int"]:
            return c_ulong
        case ["long", "long"] | ["signed", "long", "long"] | ["long", "long", "int"] | ["signed", "long", "long", "int"]:
            return c_slong_long
        case ["unsigned", "long", "long"] | ["unsigned", "long", "long", "int"]:
            return c_ulong_long
        case _:
            raise NotImplementedError(names)


_sizeof_cache = {}
_alignof_cache = {}
_offsets_cache = {}

for ts, ct in (((c_schar, c_uchar), ctypes.c_char),
               ((c_ushort, c_sshort), ctypes.c_short),
               ((c_uint, c_sint), ctypes.c_int),
               ((c_ulong, c_slong), ctypes.c_long),
               ((c_ulong_long, c_slong_long), ctypes.c_longlong),
               ):
    s = ctypes.sizeof(ct)
    a = ctypes.alignment(ct)
    for t in ts:
        _sizeof_cache[t] = s
        _alignof_cache[t] = a


def alignof(t: CType, pack=8) -> int:
    if t not in _alignof_cache:
        sizeof(t, pack)
    if t in _alignof_cache:
        return _alignof_cache[t]
    raise NotImplementedError(t)


def offsetsof(t: CStruct | CUnion, pack=8) -> int:
    if t not in _offsets_cache:
        sizeof(t, pack)
    if t in _offsets_cache:
        return _offsets_cache[t]
    raise NotImplementedError(t)


def sizeof(t: CType, pack: int = 8) -> int:
    if t in _sizeof_cache:
        return _sizeof_cache[t]
    match t:
        case CStruct(name, decls):
            offset = 0
            align = 1
            offsets = {}
            for name, ty in decls:
                e_s = sizeof(ty)
                e_a = min(pack, alignof(ty))
                if e_a > align:
                    align = e_a
                err = offset % e_a
                if err != 0:
                    offset += e_a - err
                if name is None:
                    assert isinstance(ty, (CUnion, CStruct))
                    for n, i in offsetsof(ty).items():
                        offsets[n] = offset + i
                else:
                    offsets[name] = offset
                offset += e_s
            err = offset % align
            if err != 0:
                offset += align - err
            _alignof_cache[t] = align
            _offsets_cache[t] = frozendict(offsets)
            _sizeof_cache[t] = offset or 1  # Don't allow zero size structs
        case CUnion(name, decls):
            size = 0
            align = 1
            for name, ty in decls:
                e_s = sizeof(ty)
                e_a = min(pack, alignof(ty))
                if e_a > align:
                    align = e_a
                if e_s > size:
                    size = e_s
            _alignof_cache[t] = align
            _sizeof_cache[t] = size
            assert size, t
        case CArray(_, None):
            raise ValueError(t)
        case CArray(base, dim):
            a = _alignof_cache[t] = alignof(base)
            s = sizeof(base)
            if s % a != 0:
                raise ValueError((t, a, s))
            _sizeof_cache[t] = s * dim
        case _:
            raise NotImplementedError(t)
    return _sizeof_cache[t]


def from_json(d: JSONData) -> CType:
    match d:
        case str(s) if s in _special_by_name:
            return _special_by_name[s]
        case {JSON_KEYS.TYPE: JSON_KEYS.OPAQUE_STRUCT, JSON_KEYS.NAME: name}:
            return COpaqueStruct(name)
        case {JSON_KEYS.TYPE: JSON_KEYS.OPAQUE_UNION, JSON_KEYS.NAME: name}:
            return COpaqueStruct(name)
        case {JSON_KEYS.TYPE: JSON_KEYS.FUNC, JSON_KEYS.VARARGS: varargs, JSON_KEYS.ARGS: [*args], JSON_KEYS.VALUE: rt}:
            return CFunc(tuple((d[JSON_KEYS.NAME], from_json(d[JSON_KEYS.TYPE])) for d in args), from_json(rt), varargs)
        case {JSON_KEYS.TYPE: JSON_KEYS.POINTER, JSON_KEYS.BASE: base}:
            return CPointer(from_json(base))
        case {JSON_KEYS.TYPE: JSON_KEYS.STRUCT, JSON_KEYS.NAME: name, JSON_KEYS.DECLS: [*decls]}:
            return CStruct(name, tuple((v[JSON_KEYS.NAME], from_json(v[JSON_KEYS.TYPE])) for v in decls))
        case {JSON_KEYS.TYPE: JSON_KEYS.UNION, JSON_KEYS.NAME: name, JSON_KEYS.DECLS: [*decls]}:
            return CUnion(name, tuple((v[JSON_KEYS.NAME], from_json(v[JSON_KEYS.TYPE])) for v in decls))
        case {JSON_KEYS.TYPE: JSON_KEYS.ENUM, JSON_KEYS.NAME: name, JSON_KEYS.VALUE: {**values}}:
            return CEnum(name, frozendict(values))
        case {JSON_KEYS.TYPE: JSON_KEYS.ARRAY, JSON_KEYS.BASE: base, JSON_KEYS.VALUE: dim}:
            return CArray(from_json(base), dim)
        case _:
            raise NotImplementedError(d)

def cast(ty, val):
    match ty:
        case CSpecialType(ctypes=cty):
            return cty(val).value
        case _:
            raise NotImplementedError(ty)