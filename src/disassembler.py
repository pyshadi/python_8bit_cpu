from dataclasses import dataclass
from typing import Optional, Tuple

from src.assembler import Assembler
from src.registers import Registers


class DisassemblerError(ValueError):
    pass


# opcode: (mnemonic, operand kinds), built from the assembler's table so the two can't drift apart
_INSTRUCTIONS = {opcode: (mnemonic, kinds) for mnemonic, (opcode, kinds) in Assembler.instructions.items()}


@dataclass(frozen=True)
class Instruction:
    address: int
    mnemonic: str
    operands: Tuple[Tuple[str, int], ...]  # (kind, value) with kinds 'r', 'i', 'a' as in the assembler
    bytes: Tuple[int, ...]

    @property
    def opcode(self):
        return self.bytes[0]

    @property
    def size(self):
        return len(self.bytes)

    def text(self, labels: Optional[dict] = None):
        """
        Format as assembly, e.g. "jnz, C, loop". labels maps address -> name for address operands.
        """
        parts = [self.mnemonic]
        for kind, value in self.operands:
            if kind == 'r':
                parts.append(Registers.NAMES[value])
            elif kind == 'i':
                parts.append(str(value))
            elif labels and value in labels:
                parts.append(labels[value])
            else:
                parts.append(f"0x{value:04X}")
        return ", ".join(parts)


def disassemble(code, address):
    """
    Decode the instruction that starts at address in code (a sequence of bytes).
    """
    if not 0 <= address < len(code):
        raise DisassemblerError(f"address {address:04X} is outside the program")
    opcode = code[address]
    if opcode not in _INSTRUCTIONS:
        raise DisassemblerError(f"unknown opcode {opcode:02X} at {address:04X}")
    mnemonic, kinds = _INSTRUCTIONS[opcode]

    size = 1 + sum(Assembler.OPERAND_SIZES[kind] for kind in kinds)
    if address + size > len(code):
        raise DisassemblerError(f"'{mnemonic}' at {address:04X} is cut off by the end of the program")
    raw = tuple(code[address:address + size])

    operands = []
    offset = 1
    for kind in kinds:
        if kind == 'a':
            value = raw[offset] | (raw[offset + 1] << 8)
        else:
            value = raw[offset]
            if kind == 'r' and value >= len(Registers.NAMES):
                raise DisassemblerError(f"'{mnemonic}' at {address:04X} uses invalid register {value}")
        operands.append((kind, value))
        offset += Assembler.OPERAND_SIZES[kind]

    return Instruction(address, mnemonic, tuple(operands), raw)


def disassemble_all(code, start=0, end=None):
    """
    Decode consecutive instructions from start until end (default: the end of code).
    """
    end = len(code) if end is None else end
    instructions = []
    address = start
    while address < end:
        instruction = disassemble(code, address)
        instructions.append(instruction)
        address += instruction.size
    return instructions
