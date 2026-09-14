from src.registers import Registers
from tests.helpers import run_program


def test_mvi():
    cpu = run_program("mvi, A, 20\nhlt")
    assert cpu.registers.read(Registers.A) == 20


def test_mov():
    cpu = run_program("mvi, B, 7\nmov, C, B\nhlt")
    assert cpu.registers.read(Registers.C) == 7


def test_store_and_load():
    cpu = run_program("mvi, A, 20\nst, A, 25\nld, D, 25\nhlt")
    assert cpu.ram.read(25) == 20
    assert cpu.registers.read(Registers.D) == 20


def test_addi():
    cpu = run_program("mvi, D, 20\naddi, D, 10\nhlt")
    assert cpu.registers.read(Registers.D) == 30


def test_readme_countdown_loop():
    cpu = run_program("mvi, A, 10,\nloop:,\ndec, A,\njnz, A, loop,\nhlt,")
    assert cpu.registers.read(Registers.A) == 0
    assert cpu.halted
