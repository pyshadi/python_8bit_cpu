import pytest

from src.registers import Registers
from tests.helpers import run_program


def reg(cpu, name):
    return cpu.registers.read(getattr(Registers, name))


def test_xor_instructions():
    assert reg(run_program("mvi, A, 3\nxori, A, 1\nhlt"), "A") == 2
    assert reg(run_program("mvi, B, 12\nmvi, C, 10\nxord, B, C\nhlt"), "A") == 6
    assert reg(run_program("mvi, B, 12\nst, B, 50\nmvi, C, 10\nxora, C, 50\nhlt"), "C") == 6


def test_div_instructions():
    assert reg(run_program("mvi, A, 20\nmvi, B, 5\ndiv, A, B\nhlt"), "A") == 4
    assert reg(run_program("mvi, C, 20\ndivi, C, 5\nhlt"), "C") == 4


def test_diva_writes_to_destination_register():
    cpu = run_program("mvi, B, 5\nst, B, 50\nmvi, C, 20\ndiva, C, 50\nhlt")
    assert reg(cpu, "C") == 4
    assert reg(cpu, "A") == 0


def test_jmp_skips_instruction():
    cpu = run_program("jmp, end\nmvi, C, 99\nend:\nhlt")
    assert reg(cpu, "C") == 0


@pytest.mark.parametrize("instruction, value, taken", [
    ("je", 5, True), ("je", 4, False),
    ("ja", 4, True), ("ja", 5, False),
    ("jae", 5, True), ("jae", 6, False),
    ("jb", 6, True), ("jb", 5, False),
    ("jbe", 5, True), ("jbe", 4, False),
])
def test_conditional_jumps(instruction, value, taken):
    cpu = run_program(f"mvi, B, 5\n{instruction}, B, {value}, end\nmvi, C, 99\nend:\nhlt")
    assert reg(cpu, "B") == 5  # the compared register is left untouched
    assert reg(cpu, "C") == (0 if taken else 99)


def test_push_pop_into_any_register():
    cpu = run_program("mvi, B, 7\npush, B\npop, C\nhlt")
    assert reg(cpu, "C") == 7
    assert reg(cpu, "A") == 0
    assert reg(cpu, "SP") == 255


def test_call_and_ret():
    cpu = run_program("call, sub\nmvi, B, 1\nhlt\nsub:\nmvi, C, 2\nret")
    assert reg(cpu, "B") == 1
    assert reg(cpu, "C") == 2
    assert reg(cpu, "SP") == 255
