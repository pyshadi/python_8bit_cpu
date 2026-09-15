from pathlib import Path

import pytest

from src.assembler import Assembler
from src.cpu import CPU
from src.memory import ROM, RAM
from src.registers import Registers
from src.trace import StopReason

EXAMPLES = Path(__file__).parent.parent / "examples"

# Every example needs an entry: a function checking the final machine state.
EXPECTED = {
    "bitcount.asm": lambda cpu: cpu.registers.read(Registers.C) == 5,
    "countdown.asm": lambda cpu: cpu.registers.read(Registers.A) == 0,
    "factorial.asm": lambda cpu: cpu.registers.read(Registers.A) == 120,
    "gcd.asm": lambda cpu: cpu.registers.read(Registers.A) == 6,
    "swap.asm": lambda cpu: (cpu.registers.read(Registers.B), cpu.registers.read(Registers.C)) == (42, 7),
    "fibonacci.asm": lambda cpu: [cpu.ram.read(a) for a in range(0x3F5, 0x3FF)] == [55, 34, 21, 13, 8, 5, 3, 2, 1, 1],
    "multiply.asm": lambda cpu: cpu.registers.read(Registers.D) == 42 and cpu.ram.read(0x0100) == 42,
}


def test_every_example_has_an_expectation():
    assert sorted(p.name for p in EXAMPLES.glob("*.asm")) == sorted(EXPECTED)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_runs_to_halt_with_expected_result(name):
    code = Assembler.assemble((EXAMPLES / name).read_text())
    cpu = CPU(ROM(len(code), code), RAM(1024))
    result = cpu.run_until(max_steps=10_000)
    assert result.reason == StopReason.HALTED
    assert EXPECTED[name](cpu)
