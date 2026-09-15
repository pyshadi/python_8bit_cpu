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
    "hello.asm": lambda cpu: cpu.registers.read(Registers.B) == 4,
    "countdown.asm": lambda cpu: cpu.registers.read(Registers.A) == 0,
    "factorial.asm": lambda cpu: cpu.registers.read(Registers.A) == 120,
    "gcd.asm": lambda cpu: cpu.registers.read(Registers.A) == 6,
    "swap.asm": lambda cpu: (cpu.registers.read(Registers.B), cpu.registers.read(Registers.C)) == (42, 7),
    "fibonacci.asm": lambda cpu: [cpu.ram.read(a) for a in range(0x3F5, 0x3FF)] == [55, 34, 21, 13, 8, 5, 3, 2, 1, 1],
    "multiply.asm": lambda cpu: cpu.registers.read(Registers.D) == 42 and cpu.ram.read(0x0100) == 42,
    "pattern.asm": lambda cpu: [cpu.ram.screen[i] for i in (0, 1, 2, 3, 33, 31 * 32 + 31)] == [0, 1, 2, 3, 2, 2],
}


# What each example prints with out/outc. Every example prints its result.
EXPECTED_OUTPUT = {
    "bitcount.asm": "5\n",
    "countdown.asm": "".join(f"{n}\n" for n in range(10, 0, -1)),
    "factorial.asm": "120\n",
    "fibonacci.asm": "1\n1\n2\n3\n5\n8\n13\n21\n34\n55\n",
    "gcd.asm": "6\n",
    "hello.asm": "HELLO\n1\n2\n3\n",
    "multiply.asm": "42\n",
    "pattern.asm": "",
    "swap.asm": "42\n7\n",
}


# Interactive examples never halt: they run frame after frame. Each entry checks the screen after one frame.
INTERACTIVE = {
    "keys.asm": lambda cpu: cpu.ram.screen[16 * 32 + 16] == 2,
}


def test_every_example_has_an_expectation():
    assert sorted(p.name for p in EXAMPLES.glob("*.asm")) == sorted([*EXPECTED, *INTERACTIVE])


@pytest.mark.parametrize("name", sorted(INTERACTIVE))
def test_interactive_example_draws_a_frame(name):
    code = Assembler.assemble((EXAMPLES / name).read_text())
    cpu = CPU(ROM(len(code), code), RAM(1024))
    assert cpu.run_until(max_steps=10_000, stop_at_frame=True).reason == StopReason.FRAME
    assert INTERACTIVE[name](cpu)


@pytest.mark.parametrize("name", sorted(EXPECTED))
def test_example_runs_to_halt_with_expected_result(name):
    code = Assembler.assemble((EXAMPLES / name).read_text())
    cpu = CPU(ROM(len(code), code), RAM(1024))
    result = cpu.run_until(max_steps=10_000)
    assert result.reason == StopReason.HALTED
    assert EXPECTED[name](cpu)
    assert "".join(cpu.output) == EXPECTED_OUTPUT[name]
