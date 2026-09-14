import pytest

from src.assembler import Assembler
from src.registers import Registers
from tests.helpers import run_program

PADDING = "nop\n" * 300  # pushes the code after it past address 255


def test_store_and_load_above_255():
    cpu = run_program("mvi, A, 42\nst, A, 0x3FF\nld, B, 0x3FF\nhlt", ram_size=1024)
    assert cpu.ram.read(0x3FF) == 42
    assert cpu.registers.read(Registers.B) == 42


def test_memory_operand_forms_above_255():
    cpu = run_program(
        "mvi, B, 10\nst, B, 0x200\nmvi, C, 12\nadda, C, 0x200\ncmpa, C, 0x200\npusha, 0x200\npop, D\nhlt",
        ram_size=1024)
    assert cpu.registers.read(Registers.C) == 22
    assert cpu.registers.read(Registers.D) == 10


def test_program_larger_than_256_bytes():
    source = "jmp, far\n" + "mvi, C, 99\n" * 100 + "far:\nmvi, B, 1\nhlt"
    assert len(Assembler.assemble(source)) > 256
    cpu = run_program(source)
    assert cpu.registers.read(Registers.B) == 1
    assert cpu.registers.read(Registers.C) == 0


@pytest.mark.parametrize("setup, jump", [
    ("mvi, B, 0", "jz, B, far"),
    ("mvi, B, 1", "jnz, B, far"),
    ("mvi, B, 5", "je, B, 5, far"),
    ("mvi, B, 5", "jb, B, 6, far"),
    ("mvi, A, 255\naddi, A, 1", "jc, far"),
])
def test_conditional_jumps_to_address_above_255(setup, jump):
    cpu = run_program(f"{setup}\n{jump}\n{PADDING}mvi, C, 99\nfar:\nhlt")
    assert cpu.registers.read(Registers.C) == 0


def test_call_and_ret_with_return_address_above_255():
    cpu = run_program(PADDING + "call, sub\nmvi, B, 1\nhlt\nsub:\nmvi, C, 2\nret")
    assert (cpu.registers.read(Registers.B), cpu.registers.read(Registers.C)) == (1, 2)
    assert cpu.registers.read(Registers.SP) == 255
    # return address 300 + 3 = 0x12F was pushed high byte first
    assert (cpu.ram.read(254), cpu.ram.read(253)) == (0x01, 0x2F)
