from collections import ChainMap
from typing import Any, Union

from lark.tree import pydot__tree_to_png
from lark.visitors import Interpreter

from c_headers import HeaderFinder, CDeclFunction
from c_stdlib import stdlib
from c_type import c_char_p, CType, BASE_TYPE_IDS, CPointer, c_void_p
import c_type as T  # For use in match statements
from grammar import parser

from vm_bytecode import LOAD_CONSTANT, StackState, START_CALL, ARGUMENT, CALL_VOID_VAR, CALL_VAR, CALL_VOID_FUNCTION, DISCARD, Bytecode


# TODO: I would like to have an at least partial register based VM
class Compiler(Interpreter):
    definitions: ChainMap[str, Any] = None
    constants: dict[Union[str, int], int] = None
    functions: dict[CDeclFunction, int] = None

    def __init__(self, header_finder: HeaderFinder):
        self.header_finder = header_finder

    def start(self, tree):
        self.definitions = ChainMap()
        self.constants = {}
        self.functions = {}
        cdecls, module = tree.children
        self.visit_children(cdecls)
        instructions = []
        max_size = 0
        for statement in self.visit_children(module):
            if statement is None:
                continue
            assert isinstance(statement, StackState)
            instructions.extend(statement.instructions)
            if statement.max_size > max_size:
                max_size = statement.max_size
            if statement.types:
                instructions.append(DISCARD(len(statement.types)))
        return Bytecode(tuple(self.constants), tuple(self.functions), tuple(instructions), max_size)

    def cimport_list(self, tree):
        header_name, *names = tree.children
        header = self.header_finder.get_header(eval(header_name))
        for n in names:
            self.definitions[n.value] = header.get_proc(n.value)

    def call(self, tree):
        name, *args = self.visit_children(tree)
        decl = self.definitions[name]
        assert isinstance(decl, CDeclFunction), decl
        arg_types = []
        instructions = [START_CALL(self._get_function(decl), len(args))]
        stack_size = 1
        max_stack_size = 1
        for i, a in enumerate(args):
            assert isinstance(a, StackState), a
            assert len(a.types) == 1, a
            stack_size += a.max_size
            if stack_size > max_stack_size:
                max_stack_size = stack_size
            arg_types.append(t := a.types[0])
            if i < len(decl.arguments):
                assert t == decl.arguments[i][1], (t, decl.arguments[i])
            else:
                assert decl.varargs
            instructions.extend(a.instructions)
            instructions.append(ARGUMENT(i, self._get_type_id(a.types[0])))
            stack_size -= a.max_size
            stack_size += 1
            if stack_size > max_stack_size:
                max_stack_size = stack_size
        st = []
        match decl.varargs, decl.return_type:
            case True, T.c_void:
                instructions.append(CALL_VOID_VAR(len(args)))
            case False, T.c_void:
                instructions.append(CALL_VOID_FUNCTION(len(args)))
            case True, t:
                st.append(t)
                instructions.append(CALL_VAR(len(args), len(decl.arguments), self._get_type_id(decl.return_type)))
            case False, t:
                st.append(t)
                instructions.append(CALL_VOID_VAR(len(args), len(decl.arguments)))
        return StackState(tuple(st), tuple(instructions), max_stack_size)

    def string(self, tree):
        tok, = tree.children
        s = eval(tok)
        i = self._get_constant(s)
        return StackState((c_char_p,), (LOAD_CONSTANT(i),), 1)

    def __default__(self, tree):
        raise NotImplementedError(tree)

    def _get_type_id(self, t: CType):
        if isinstance(t, CPointer):
            return BASE_TYPE_IDS[c_void_p]
        else:
            return BASE_TYPE_IDS[t]

    def _get_function(self, decl):
        if decl not in self.functions:
            self.functions[decl] = len(self.functions)
        return self.functions[decl]

    def _get_constant(self, value):
        if value not in self.constants:
            self.constants[value] = len(self.constants)
        return self.constants[value]


def compile(text: str) -> Bytecode:
    tree = parser.parse(text)
    pydot__tree_to_png(tree, "test.png")
    return Compiler(stdlib).visit(tree)
