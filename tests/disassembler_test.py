from pathlib import Path

import pytest

from src.assembler import Assembler
from src.disassembler import DisassemblerError, disassemble, disassemble_all
from src.registers import Registers

FIBONACCI = (Path(__file__).parent.parent / "examples" / "fibonacci.asm").read_text()
SAMPLE_OPERANDS = {'r': "B", 'i': "7", 'a': "0x0123"}


def test_every_instruction_round_trips():
    source = "\n".join(
        ", ".join([mnemonic] + [SAMPLE_OPERANDS[kind] for kind in kinds])
        for mnemonic, (_, kinds) in Assembler.instructions.items()
    )
    code = Assembler.assemble(source)
    instructions = disassemble_all(code)

    assert [i.mnemonic for i in instructions] == list(Assembler.instructions)
    assert [i.text() for i in instructions] == source.splitlines()
    assert Assembler.assemble("\n".join(i.text() for i in instructions)) == code


def test_instruction_fields():
    instruction = disassemble(Assembler.assemble("nop\njnz, C, 0x1234"), 1)
    assert instruction.address == 1
    assert instruction.mnemonic == "jnz"
    assert instruction.opcode == 0x28
    assert instruction.operands == (('r', Registers.C), ('a', 0x1234))
    assert instruction.bytes == (0x28, 0x02, 0x34, 0x12)
    assert instruction.size == 4


def test_address_operands_use_labels_when_given():
    program = Assembler.assemble_program(FIBONACCI)
    labels = {address: name for name, address in program.labels.items()}
    texts = [i.text(labels) for i in disassemble_all(program.bytecode)]
    assert texts[:5] == ["mvi, A, 0", "mvi, B, 1", "mvi, C, 10", "push, B", "call, next"]
    assert "jnz, C, loop" in texts


def test_disassemble_all_range():
    code = Assembler.assemble("mvi, A, 1\ninc, A\nhlt")
    assert [i.mnemonic for i in disassemble_all(code, start=3)] == ["inc", "hlt"]
    assert [i.mnemonic for i in disassemble_all(code, end=3)] == ["mvi"]


@pytest.mark.parametrize("code, address, message", [
    ([0x99], 0, "unknown opcode 99 at 0000"),
    ([0x03, 0x00], 0, "'ld' at 0000 is cut off"),
    ([0x11, 0x20], 0, "invalid register 32"),
    ([0x00], 5, "outside the program"),
])
def test_invalid_code_raises(code, address, message):
    with pytest.raises(DisassemblerError, match=message):
        disassemble(code, address)


def test_source_map():
    program = Assembler.assemble_program(FIBONACCI)
    assert program.labels == {"loop": 0x09, "next": 0x15}
    assert program.line_addresses == {
        2: 0x00, 3: 0x03, 4: 0x06, 5: 0x09, 6: 0x0B, 7: 0x0E, 8: 0x10, 9: 0x14,
        11: 0x15, 12: 0x18, 13: 0x1B, 14: 0x1E, 15: 0x21, 16: 0x23,
    }
    assert program.address_lines[0x18] == 12
    assert program.bytecode == Assembler.assemble(FIBONACCI)


def test_register_names_match_assembler():
    assert {name: index for index, name in enumerate(Registers.NAMES)} == Assembler.register_map
