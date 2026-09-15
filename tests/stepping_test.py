from pathlib import Path

import pytest

from src.assembler import Assembler
from src.cpu import CPU
from src.memory import ROM, RAM
from src.registers import Registers
from src.trace import StopReason

FIBONACCI = (Path(__file__).parent.parent / "examples" / "fibonacci.asm").read_text()
A, B, C, E, F, SP = Registers.A, Registers.B, Registers.C, Registers.E, Registers.F, Registers.SP


def fibonacci_cpu(ram_size=1024):
    program = Assembler.assemble_program(FIBONACCI)
    cpu = CPU(ROM(len(program.bytecode), program.bytecode), RAM(ram_size))
    return cpu, {address: name for name, address in program.labels.items()}


def test_step_records_match_expected_trace():
    cpu, labels = fibonacci_cpu()
    for _ in range(52):
        cpu.step()
    records = [cpu.step() for _ in range(8)]

    expected = [
        # cycle, address, text, register writes, RAM writes, next address, jumped
        (53, 0x001B, "mov, B, A", {B: (0x08, 0x0D)}, {}, 0x001E, False),
        (54, 0x001E, "mov, A, E", {A: (0x0D, 0x08)}, {}, 0x0021, False),
        (55, 0x0021, "ret", {SP: (0x3F7, 0x3F9)}, {}, 0x000E, True),
        (56, 0x000E, "dec, C", {C: (0x05, 0x04), F: (0x00, 0x00)}, {}, 0x0010, False),
        (57, 0x0010, "jnz, C, loop", {}, {}, 0x0009, True),
        (58, 0x0009, "push, B", {SP: (0x3F9, 0x3F8)}, {0x3F8: (0x00, 0x0D)}, 0x000B, False),
        (59, 0x000B, "call, next", {SP: (0x3F8, 0x3F6)}, {0x3F6: (0x00, 0x0E), 0x3F7: (0x0E, 0x00)}, 0x0015, True),
        (60, 0x0015, "mov, E, B", {E: (0x08, 0x0D)}, {}, 0x0018, False),
    ]
    actual = [(r.cycle, r.address, r.instruction.text(labels), r.register_writes, r.ram_writes,
               r.next_address, r.jumped) for r in records]
    assert actual == expected
    assert not any(r.halted for r in records)


def test_write_logs_are_off_outside_step():
    cpu, _ = fibonacci_cpu()
    cpu.step()
    assert cpu.registers.write_log is None and cpu.ram.write_log is None


def test_last_step_reports_halt():
    cpu, _ = fibonacci_cpu()
    records = []
    result = cpu.run_until(on_step=records.append)
    assert result.reason == StopReason.HALTED
    assert result.steps == len(records) == cpu.cycles == 94
    assert records[-1].instruction.mnemonic == "hlt" and records[-1].halted
    assert [cpu.ram.read(a) for a in range(0x3F5, 0x3FF)] == [55, 34, 21, 13, 8, 5, 3, 2, 1, 1]


def test_step_on_halted_cpu_raises():
    cpu, _ = fibonacci_cpu()
    cpu.run_until()
    with pytest.raises(RuntimeError, match="halted"):
        cpu.step()


def test_breakpoints_stop_before_the_instruction_and_resume():
    cpu, _ = fibonacci_cpu()
    cpu.breakpoints.add(0x0018)  # add, A, B

    first = cpu.run_until()
    assert (first.reason, first.steps) == (StopReason.BREAKPOINT, 6)
    assert cpu.registers.read(Registers.PC) == 0x0018
    assert cpu.registers.read(A) == 0  # the add has not run yet

    second = cpu.run_until()  # continues past the breakpoint it is sitting on
    assert (second.reason, second.steps) == (StopReason.BREAKPOINT, 9)
    assert cpu.cycles == 15


def test_step_limit():
    cpu, _ = fibonacci_cpu()
    result = cpu.run_until(max_steps=5)
    assert (result.reason, result.steps) == (StopReason.STEP_LIMIT, 5)
    assert cpu.cycles == 5 and not cpu.halted


def test_snapshot_and_restore_replay_identically():
    cpu, _ = fibonacci_cpu()
    cpu.run_until(max_steps=30)
    snapshot = cpu.snapshot()

    cpu.run_until()
    finished = cpu.snapshot()

    cpu.restore(snapshot)
    assert cpu.snapshot() == snapshot
    cpu.run_until()
    assert cpu.snapshot() == finished


def test_restore_rejects_other_ram_size():
    cpu, _ = fibonacci_cpu()
    other, _ = fibonacci_cpu(ram_size=256)
    with pytest.raises(ValueError, match="1024 bytes of RAM, but this CPU has 256"):
        other.restore(cpu.snapshot())


def test_reset_restores_power_on_state_and_keeps_breakpoints():
    cpu, _ = fibonacci_cpu()
    power_on = cpu.snapshot()
    cpu.breakpoints.add(0x0018)
    cpu.run_until()
    cpu.breakpoints.clear()
    cpu.breakpoints.add(0x0014)
    cpu.run_until()

    cpu.reset()
    assert cpu.snapshot() == power_on
    assert cpu.breakpoints == {0x0014}


def test_errors_propagate_from_step():
    code = Assembler.assemble("pop, A")
    cpu = CPU(ROM(len(code), code), RAM(16))
    with pytest.raises(IndexError, match="stack underflow"):
        cpu.step()
    assert cpu.registers.write_log is None and cpu.ram.write_log is None
