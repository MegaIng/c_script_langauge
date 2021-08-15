from __future__ import annotations

import json
import re
from dataclasses import dataclass, field, fields
from hashlib import sha256, md5
from os import remove
from pathlib import Path
from subprocess import check_output
from typing import Optional, TypeAlias

import pycparserext.ext_c_parser
from frozendict import frozendict
from pycparser import c_ast
from pycparser.plyparser import ParseError
from pycparserext.ext_c_parser import FuncDeclExt
from wheel.util import urlsafe_b64encode

import c_type
from c_headers import CDeclFunction
from c_type import CType, CPointer, COpaqueStruct, CStruct, CArray, CFunc, CEnum, CUnion, sizeof, COpaqueUnion, cast, JSON_KEYS
from utils import JSONData


@dataclass(frozen=True)
class CMacro:
    name: str
    args: Optional[tuple[str, ...]]
    replacement: str

    def __repr__(self):
        if self.args is None:
            return f"<{self.name}={self.replacement!r}>"
        else:
            return f"<{self.name}({','.join(self.args)})={self.replacement}>"

    def to_json(self) -> JSONData:
        return {  # Name is stored by the parent
            JSON_KEYS.ARGS: self.args,
            JSON_KEYS.VALUE: self.replacement,
        }

    @classmethod
    def from_json(cls, n: str, d: JSONData) -> CMacro:
        return cls(n, d[JSON_KEYS.ARGS], d[JSON_KEYS.VALUE])


@dataclass
class FullHeader:
    name: str
    macros: dict[str, CMacro] = field(default_factory=dict)
    functions: dict[str, CType] = field(default_factory=dict)
    variables: dict[str, CType] = field(default_factory=dict)
    types: dict[str, CType] = field(default_factory=dict)
    structs: dict[str, CType] = field(default_factory=dict)
    unions: dict[str, CType] = field(default_factory=dict)
    enums: dict[str, CType] = field(default_factory=dict)
    enum_values: dict[str, tuple[int, str]] = field(default_factory=dict)

    def to_json(self) -> JSONData:
        out = {}
        for f in fields(self):
            v = getattr(self, f.name)
            if f.name == "name":
                out[f.name] = v
            elif f.name == "enum_values":
                continue
            else:
                # Everything else are dictionaries with CType/CMacro instances as values
                out[f.name] = {
                    n: t.to_json()
                    for n, t in v.items()
                }
        return out

    def get_constant_int(self, name: str):
        if name in self.macros:
            return int(self.macros[name].replacement)
        raise NotImplementedError(name)

    def freeze(self):
        for f in fields(self):
            v = getattr(self, f.name)
            if isinstance(v, dict):
                setattr(self, f.name, frozendict(v))

    @classmethod
    def from_json(cls, data: JSONData):
        self = cls(data["name"])
        for f in fields(self):
            if f.name == "name":
                continue
            elif f.name == "enum_values":
                continue
            v = data[f.name]
            if f.name == "macros":
                setattr(self, f.name, {
                    n: CMacro.from_json(n, d)
                    for n, d in v.items()
                })
            else:
                setattr(self, f.name, {
                    n: c_type.from_json(d)
                    for n, d in v.items()
                })
        for n, e in self.enums.items():
            assert isinstance(e, CEnum)
            for vn, v in e.values.items():
                self.enum_values[vn] = (v, n)
        return self


def preprocess_code(code, cpp_path='cpp', cpp_args: str | list[str] = ''):
    path_list = [cpp_path]
    if isinstance(cpp_args, list):
        path_list += cpp_args
    elif cpp_args != '':
        path_list += [cpp_args]

    try:
        # Note the use of universal_newlines to treat all newlines
        # as \n for Python's purpose
        text = check_output(path_list, universal_newlines=True, input=code)
    except OSError as e:
        raise RuntimeError("Unable to invoke 'cpp'.  " +
                           'Make sure its path was passed correctly\n' +
                           ('Original error: %s' % e))

    return text


class DeclarationExtraction(c_ast.NodeVisitor):
    def __init__(self, headers: FullHeader):
        self.header = headers

    def handle_param(self, node) -> tuple[Optional[str], CType]:
        match node:
            case c_ast.Typename(name=None, type=type):
                return None, self.to_c_type(type)
            case c_ast.Decl(name=name, type=type):
                return name, self.to_c_type(type)
            case _:
                raise NotImplementedError(node)

    def get_value(self, node) -> int:
        match node:
            case c_ast.Constant(type='int', value=value):
                return eval(value)
            case c_ast.Cast(to_type=c_ast.Typename(type=type), expr=expr):
                expr = self.get_value(expr)
                ty = self.to_c_type(type)
                return cast(ty, expr)
            case c_ast.UnaryOp(op="sizeof", expr=c_ast.Typename(type=type)):
                return sizeof(self.to_c_type(type))
            case c_ast.UnaryOp(op=op, expr=expr):
                expr = self.get_value(expr)
                match op:
                    case '-':
                        return -expr
                    case '+':
                        return +expr
                    case _:
                        raise NotImplementedError(op)
            case c_ast.BinaryOp(op=op, left=left, right=right):
                left = self.get_value(left)
                right = self.get_value(right)
                match op:
                    case '+':
                        return left + right
                    case '>>':
                        return left >> right
                    case '<<':
                        return left << right
                    case '|':
                        return left | right
                    case _:
                        raise NotImplementedError(op)
            case c_ast.ID(name=name) if name in self.header.enum_values:
                return self.header.enum_values[name][0]
            case _:
                node.show(showcoord=True)
                raise NotImplementedError(node)

    def to_c_type(self, node: c_ast.Node) -> CType:
        match node:
            case c_ast.IdentifierType(names=[name]) if name in self.header.types:
                return self.header.types[name]
            case c_ast.IdentifierType(names=[*names]):
                return c_type.get_from_names(names)
            case c_ast.TypeDecl(type=inner):
                return self.to_c_type(inner)
            case c_ast.PtrDecl(type=base):
                return CPointer(self.to_c_type(base))
            case c_ast.Struct(name=str(name), decls=None):
                s = COpaqueStruct(name)
                if name not in self.header.structs:
                    self.header.structs[name] = s
                # While we could return the correct result here, that will only increase the size of cache files.
                return s
            case c_ast.Struct(name=name, decls=[*decls]):
                s = CStruct(name, tuple(
                    (decl.name, self.to_c_type(decl.type)) for decl in decls
                ))
                if name is not None:
                    if name not in self.header.structs:
                        self.header.structs[name] = s
                    elif isinstance(self.header.structs[name], COpaqueStruct):
                        self.header.structs[name] = s
                    else:
                        assert self.header.structs[name] == s, (s, self.header.structs[name])
                return s
            case c_ast.Union(name=str(name), decls=None):
                s = COpaqueUnion(name)
                if name not in self.header.unions:
                    self.header.unions[name] = s
                return s
            case c_ast.Union(name=name, decls=[*decls]):
                s = CUnion(name, tuple(
                    (decl.name, self.to_c_type(decl.type)) for decl in decls
                ))
                if name is not None:
                    if name not in self.header.unions:
                        self.header.unions[name] = s
                    elif isinstance(self.header.unions[name], COpaqueUnion):
                        self.header.unions[name] = s
                    else:
                        assert self.header.unions[name] == s, (s, self.header.unions[name])
                return s
            case c_ast.Enum(name=name, values=c_ast.EnumeratorList(enumerators=[*values])):

                out = {}
                value = 0
                for e in values:
                    if e.value is not None:
                        value = self.get_value(e.value)
                    out[e.name] = value
                    self.header.enum_values[e.name] = value, name
                    value += 1
                e = CEnum(name, frozendict(out))
                if name is not None:
                    if name not in self.header.enums:
                        self.header.enums[name] = e
                    else:
                        assert self.header.enums[name] == e
                return e
            case c_ast.ArrayDecl(type=base, dim=None):
                return CArray(self.to_c_type(base), None)
            case c_ast.ArrayDecl(type=base, dim=value):
                return CArray(self.to_c_type(base), self.get_value(value))
            case FuncDeclExt(args=c_ast.ParamList(params=[*params, c_ast.EllipsisParam()]), type=return_type):
                return CFunc(tuple(self.handle_param(param) for param in params), self.to_c_type(return_type), True)
            case FuncDeclExt(args=c_ast.ParamList(params=[*params]), type=return_type):
                return CFunc(tuple(self.handle_param(param) for param in params), self.to_c_type(return_type), False)
            case FuncDeclExt(args=c_ast.ParamList(params=None) | None, type=return_type):
                return CFunc((), self.to_c_type(return_type), False)
            case _:
                node.show(showcoord=True)
                raise NotImplementedError(node)

    # def visit_FuncDecl(self, node):
    #     ty = c_ast.TypeDecl(declname='_hidden',
    #                         quals=[],
    #                         type=c_ast.IdentifierType(['int']))
    #     newdecl = c_ast.Decl(
    #         name='_hidden',
    #         quals=[],
    #         storage=[],
    #         funcspec=[],
    #         type=ty,
    #         init=None,
    #         bitsize=None,
    #         coord=node.coord)
    #     if node.args:
    #         node.args.params.append(newdecl)
    #     else:
    #         node.args = c_ast.ParamList(params=[newdecl])

    def visit_Pragma(self, node: c_ast.Pragma):
        pass  # TODO: Currently, we are doing nothing with pragmas. We might need to deal with pack

    def visit_FuncDef(self, node: c_ast.FuncDef):
        self.visit(node.decl)

    def visit_Decl(self, node: c_ast.Decl):
        if isinstance(node.type, (c_ast.FuncDecl, pycparserext.ext_c_parser.FuncDeclExt)):
            self.header.functions[node.name] = self.to_c_type(node.type)
        else:
            t = self.to_c_type(node.type)
            if node.name is not None:
                self.header.variables[node.name] = t

    def visit_Typedef(self, node: c_ast.Typedef):
        ty = self.to_c_type(node.type)
        self.header.types[node.name] = ty

    def generic_visit(self, node):
        assert False, node

    def visit_FileAST(self, node: c_ast.FileAST):
        super(DeclarationExtraction, self).generic_visit(node)


c_parser = pycparserext.ext_c_parser.GnuCParser()

CACHE_DIR = Path("header_cache")


def invalidate_cache():
    for f in CACHE_DIR.glob("*.h.json"):
        remove(f)


def _cache_name(name: str):
    assert name.endswith(".h")
    h = md5(name.encode()).hexdigest()
    safe_name = re.sub('[^A-Za-z0-9.]+', '-', name)
    return f"{h}-{safe_name}.json"


def extract_header(header_name: str, no_cache: bool = False) -> FullHeader:
    if not no_cache:
        cache_name = _cache_name(header_name)
        if (CACHE_DIR / cache_name).exists():
            with (CACHE_DIR / cache_name).open("r") as f:
                data = json.load(f)
            return FullHeader.from_json(data)
    cpp_args = ["-x", "c", "-D__extension__=", "-D__attribute__(x)="]
    definitions = preprocess_code(f"#include <{header_name}>", cpp_path="cpp.exe",
                                  cpp_args=[*cpp_args, "-dM"])
    full_code = preprocess_code(f"#include <{header_name}>", cpp_path="cpp.exe",
                                cpp_args=cpp_args)
    headers = FullHeader(header_name)

    for line in definitions.splitlines():
        if m := re.match("#define (\w+)\(((?:\w+(?:,\w+)*)?)\) (.*)", line):
            name, args, repl = m.groups()
            args = args.split(',')
            headers.macros[name] = CMacro(name, args, repl)
        elif m := re.match("#define (\w+) (.*)", line):
            name, repl = m.groups()
            headers.macros[name] = CMacro(name, None, repl)
        else:
            print("Unknown line", line)

    try:
        ast = c_parser.parse(full_code)
    except ParseError as e:
        m = re.fullmatch("((?:[cC]:)?[^:]+):(\d+):(\d+):(.*)", str(e))
        path, line, column, message = m.groups()
        raise ParseError(f"\n    File \"{path}\", line {line}, column {column}\n        {message}")
    DeclarationExtraction(headers).visit(ast)
    headers.freeze()
    if not no_cache:
        data = headers.to_json()
        with (CACHE_DIR / cache_name).open("w") as f:
            json.dump(data, f, separators=(',', ':'))
    return headers
