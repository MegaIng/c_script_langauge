from collections import ChainMap
from typing import Any

from lark import Interpreter
from lark.tree import pydot__tree_to_png

from grammar import parser


class Compiler(Interpreter):
    definitions: ChainMap[str, Any] = None

    def start(self, tree):
        cdecls, module = tree.children
        self.definitions = ChainMap()


def compile(text: str):
    tree = parser.parse(text)
    pydot__tree_to_png(tree, "test.png")
    return Compiler().visit(tree)
