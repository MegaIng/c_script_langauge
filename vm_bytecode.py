from __future__ import annotations

from dataclasses import dataclass

from frozendict import frozendict

from c_headers import CDeclFunction
from c_type import CType


@dataclass(frozen=True, slots=True)
class Instruction:
    name: str
    id: int
    argc: int = 0

    def __call__(self, *args) -> AppliedInstruction:
        assert 0 <= self.id <= 255, self
        assert all(isinstance(a, int) for a in args), (self, args)
        assert all(0 <= a <= 255 for a in args), (self, args)
        assert len(args) == self.argc, (self, args)
        return AppliedInstruction(self, args)


LOAD_CONSTANT = Instruction("LOAD_CONSTANT", 1, 1)
DISCARD = Instruction("DISCARD", 2, 1)

START_CALL = Instruction("START_CALL", 3, 2)
ARGUMENT = Instruction("ARGUMENT", 4, 2)

CALL_FUNCTION = Instruction("CALL_FUNCTION", 5, 2)
CALL_VOID_FUNCTION = Instruction("CALL_VOID_FUNCTION", 6, 1)
CALL_VAR = Instruction("CALL_VAR", 7, 3)
CALL_VOID_VAR = Instruction("CALL_VOID_VAR", 8, 2)


@dataclass(frozen=True, slots=True)
class AppliedInstruction:
    ins: Instruction
    args: tuple[int, ...]

    @property
    def bytes(self):
        return self.ins.id, *self.args


@dataclass(frozen=True, slots=True)
class StackState:
    types: tuple[CType, ...]
    instructions: tuple[AppliedInstruction, ...]
    max_size: int


@dataclass(frozen=True, slots=True)
class Bytecode:
    constants: tuple[str | int, ...]
    function_decls: tuple[CDeclFunction, ...]
    instructions: tuple[AppliedInstruction, ...]
    max_size: int

    def to_json(self):
        return {
            "constants": self.constants,
            "functions": [{"dll": d.header.know_dll, "name": d.name} for d in self.function_decls],
            "instructions": [v for i in self.instructions for v in i.bytes],
            "max_size": self.max_size
        }
