from src.assembler import Assembler
from src.cpu import CPU
from src.memory import ROM, RAM


def run_program(source, ram_size=256, max_steps=1000):
    """
    Assemble and run a program until it halts. Fails if it doesn't halt within max_steps.
    """
    code = Assembler.assemble(source)
    cpu = CPU(ROM(len(code) + 1, code), RAM(ram_size))
    steps = 0
    while not cpu.halted:
        assert steps < max_steps, f"program did not halt within {max_steps} steps"
        cpu.run()
        steps += 1
    return cpu
