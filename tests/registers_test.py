import pytest

from src.alu import Flags
from src.registers import Registers
from tests.helpers import run_program


def test_general_purpose_registers_are_8_bit():
    registers = Registers()
    registers.write(Registers.A, 1000)
    assert registers.read(Registers.A) == 1000 & 0xFF


def test_sp_and_pc_are_16_bit():
    registers = Registers()
    registers.write(Registers.SP, 2047)
    registers.write(Registers.PC, 0x1_0005)
    assert registers.read(Registers.SP) == 2047
    assert registers.read(Registers.PC) == 0x0005


def test_write_rejects_invalid_index():
    registers = Registers()
    with pytest.raises(IndexError):
        registers.write(-1, 5)
    with pytest.raises(IndexError):
        registers.write(16, 5)


def test_dec_wraps_from_0_to_255():
    cpu = run_program("mvi, A, 0\ndec, A\nhlt")
    assert cpu.registers.read(Registers.A) == 255


def test_inc_wraps_from_255_to_0_and_sets_flags():
    cpu = run_program("mvi, A, 255\ninc, A\nhlt")
    assert cpu.registers.read(Registers.A) == 0
    assert cpu.registers.read(Registers.F) == Flags.ZERO | Flags.CARRY


def test_arithmetic_carry_is_visible_in_f_register():
    cpu = run_program("mvi, A, 255\nmvi, B, 1\nadd, A, B\nhlt")
    assert cpu.registers.read(Registers.F) & Flags.CARRY


def test_jc_jumps_after_arithmetic_carry():
    cpu = run_program("mvi, A, 255\naddi, A, 1\njc, taken\nmvi, B, 1\ntaken:\nhlt")
    assert cpu.registers.read(Registers.B) == 0


def test_jnc_jumps_without_carry():
    cpu = run_program("mvi, A, 1\naddi, A, 1\njnc, taken\nmvi, B, 1\ntaken:\nhlt")
    assert cpu.registers.read(Registers.B) == 0


def test_cmp_uses_same_flag_layout_as_alu():
    cpu = run_program("mvi, A, 5\nmvi, B, 10\ncmp, A, B\nhlt")
    assert cpu.registers.read(Registers.F) == Flags.CARRY | Flags.SIGN
    cpu = run_program("mvi, A, 7\ncmpi, A, 7\nhlt")
    assert cpu.registers.read(Registers.F) == Flags.ZERO
