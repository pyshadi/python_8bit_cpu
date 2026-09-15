import pytest

from src.alu import Flags
from src.decoder import StackOverflowError, StackUnderflowError
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


def test_nested_calls():
    cpu = run_program("call, outer\nhlt\nouter:\ncall, inner\nret\ninner:\nmvi, C, 9\nret")
    assert reg(cpu, "C") == 9
    assert reg(cpu, "SP") == 255
    assert cpu.halted


# B = 12, C / immediate / RAM[40] = 10
BINARY_RESULTS = {"add": 22, "sub": 2, "mul": 120, "div": 1, "and": 8, "or": 14, "xor": 6}
REGISTER_FORMS = {"add": "add", "sub": "sub", "mul": "mul", "div": "div", "and": "andd", "or": "ord", "xor": "xord"}
IMMEDIATE_FORMS = {"add": "addi", "sub": "subi", "mul": "muli", "div": "divi", "and": "andi", "or": "ori", "xor": "xori"}
MEMORY_FORMS = {"add": "adda", "sub": "suba", "mul": "mula", "div": "diva", "and": "anda", "or": "ora", "xor": "xora"}


@pytest.mark.parametrize("operation", BINARY_RESULTS)
def test_register_register_form_writes_accumulator(operation):
    cpu = run_program(f"mvi, B, 12\nmvi, C, 10\n{REGISTER_FORMS[operation]}, B, C\nhlt")
    assert reg(cpu, "A") == BINARY_RESULTS[operation]
    assert (reg(cpu, "B"), reg(cpu, "C")) == (12, 10)


@pytest.mark.parametrize("operation", BINARY_RESULTS)
def test_register_immediate_form_writes_register(operation):
    cpu = run_program(f"mvi, B, 12\n{IMMEDIATE_FORMS[operation]}, B, 10\nhlt")
    assert reg(cpu, "B") == BINARY_RESULTS[operation]
    assert reg(cpu, "A") == 0


@pytest.mark.parametrize("operation", BINARY_RESULTS)
def test_register_memory_form_writes_register(operation):
    cpu = run_program(f"mvi, C, 10\nst, C, 40\nmvi, B, 12\n{MEMORY_FORMS[operation]}, B, 40\nhlt")
    assert reg(cpu, "B") == BINARY_RESULTS[operation]
    assert reg(cpu, "A") == 0


def test_rotate_instructions():
    assert reg(run_program("mvi, B, 0b10001100\nrtl, B\nhlt"), "B") == 0b00011001
    assert reg(run_program("mvi, B, 0b1100\nrtr, B\nhlt"), "B") == 0b0110


def test_shift_instructions():
    assert reg(run_program("mvi, B, 0b00001111\nshl, B, 2\nhlt"), "B") == 0b00111100
    assert reg(run_program("mvi, B, 0b00111100\nshr, B, 2\nhlt"), "B") == 0b00001111


@pytest.mark.parametrize("program", [
    "mvi, A, 5\nmvi, B, 10\ncmp, A, B\nhlt",
    "mvi, A, 5\ncmpi, A, 10\nhlt",
    "mvi, B, 10\nst, B, 40\nmvi, A, 5\ncmpa, A, 40\nhlt",
])
def test_compare_forms_set_flags_only(program):
    cpu = run_program(program)
    assert reg(cpu, "F") == Flags.CARRY | Flags.SIGN
    assert reg(cpu, "A") == 5


@pytest.mark.parametrize("instruction, value, taken", [
    ("jz", 0, True), ("jz", 1, False),
    ("jnz", 1, True), ("jnz", 0, False),
])
def test_zero_jumps(instruction, value, taken):
    cpu = run_program(f"mvi, B, {value}\n{instruction}, B, end\nmvi, C, 99\nend:\nhlt")
    assert reg(cpu, "C") == (0 if taken else 99)


def test_pushi_and_pusha():
    cpu = run_program("pushi, 42\nmvi, B, 9\nst, B, 40\npusha, 40\npop, C\npop, D\nhlt")
    assert (reg(cpu, "C"), reg(cpu, "D")) == (9, 42)
    assert reg(cpu, "SP") == 255


def test_out_prints_decimal_lines_and_outc_prints_characters():
    cpu = run_program("mvi, A, 42\nout, A\nmvi, B, 72\noutc, B\nmvi, B, 105\noutc, B\nout, SP\nhlt")
    assert "".join(cpu.output) == "42\nHi255\n"


def test_inv():
    cpu = run_program("mvi, B, 0b10100101\ninv, B\nhlt")
    assert reg(cpu, "B") == 0b01011010
    cpu = run_program("mvi, B, 255\ninv, B\nhlt")
    assert reg(cpu, "B") == 0
    assert reg(cpu, "F") == Flags.ZERO


def test_sar_keeps_sign_and_sets_carry_from_shifted_bit():
    cpu = run_program("mvi, B, 0b10000011\nsar, B\nhlt")
    assert reg(cpu, "B") == 0b11000001
    assert reg(cpu, "F") == Flags.CARRY
    cpu = run_program("mvi, B, 0b00000100\nsar, B\nhlt")
    assert reg(cpu, "B") == 0b00000010
    assert reg(cpu, "F") == 0


def test_stack_can_be_filled_and_emptied():
    source = "pushi, 1\n" * 15 + "pop, A\n" * 15 + "hlt"
    cpu = run_program(source, ram_size=16)  # SP starts at 15, so 15 bytes fit
    assert reg(cpu, "SP") == 15


def test_push_onto_full_stack_raises():
    with pytest.raises(StackOverflowError):
        run_program("pushi, 1\n" * 16 + "hlt", ram_size=16)


@pytest.mark.parametrize("program", ["pop, A\nhlt", "ret"])
def test_pop_or_ret_on_empty_stack_raises(program):
    with pytest.raises(StackUnderflowError):
        run_program(program)
