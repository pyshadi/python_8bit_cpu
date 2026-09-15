from dataclasses import dataclass
from typing import Dict, Tuple

from src.disassembler import Instruction
from src.registers import Registers

CONDITIONAL_JUMPS = {"jc", "jnc", "jz", "jnz", "je", "ja", "jae", "jb", "jbe"}


@dataclass(frozen=True)
class StepRecord:
    """
    What one instruction did, as returned by CPU.step().
    """
    cycle: int                                   # 1 for the first instruction after a reset
    address: int                                 # where the instruction started
    instruction: Instruction
    register_writes: Dict[int, Tuple[int, int]]  # register index -> (old, new); PC is left out
    ram_writes: Dict[int, Tuple[int, int]]       # RAM address -> (old, new)
    next_address: int                            # PC after the instruction
    halted: bool

    @property
    def jumped(self):
        """True when execution did not continue with the next instruction in the program."""
        return self.next_address != self.address + self.instruction.size


class StopReason:
    HALTED = "halted"
    BREAKPOINT = "breakpoint"
    STEP_LIMIT = "step_limit"


@dataclass(frozen=True)
class RunResult:
    reason: str  # one of StopReason
    steps: int   # instructions executed by this run


@dataclass(frozen=True)
class Snapshot:
    """
    Complete machine state, from CPU.snapshot(). ROM is not included because it can't change.
    """
    registers: Tuple[int, ...]
    ram: Tuple[int, ...]
    halted: bool
    cycles: int


# --- Formatting ------------------------------------------------------------------

TRACE_HEADER = f"{'cycle':>6}  addr  {'bytes':<11}  {'instruction':<16}  effect"


def format_effect(record, labels=None):
    """
    Describe a step's effect, e.g. "[03F8] ← 0D · SP ← 03F8" or "taken → 0009".
    """
    parts = []
    for reg, (_, new) in record.register_writes.items():
        width = 4 if reg in (Registers.SP, Registers.PC) else 2
        parts.append(f"{Registers.NAMES[reg]} ← {new:0{width}X}")
    for address, (_, new) in record.ram_writes.items():
        parts.append(f"[{address:04X}] ← {new:02X}")

    target = f"{record.next_address:04X}"
    if labels and record.next_address in labels:
        target += f" ({labels[record.next_address]})"
    if record.instruction.mnemonic in CONDITIONAL_JUMPS:
        parts.append(f"taken → {target}" if record.jumped else "not taken")
    elif record.jumped:
        parts.append(f"PC ← {target}")
    if record.halted:
        parts.append("halted")
    return " · ".join(parts)


def format_record(record, labels=None):
    """
    One trace line: cycle, address, bytes, instruction and effect.
    """
    raw = " ".join(f"{b:02X}" for b in record.instruction.bytes)
    text = record.instruction.text(labels)
    return f"{record.cycle:>6}  {record.address:04X}  {raw:<11}  {text:<16}  {format_effect(record, labels)}".rstrip()


def format_flags(flags):
    """
    Letters of the set flags, e.g. "Z C", or "-" when none are set.
    """
    from src.alu import Flags
    names = [name for name, bit in (("Z", Flags.ZERO), ("C", Flags.CARRY), ("V", Flags.OVERFLOW), ("S", Flags.SIGN))
             if flags & bit]
    return " ".join(names) or "-"


def format_registers(registers):
    """
    Two lines: the 8-bit general purpose registers, then PC, SP and F with its flags.
    """
    general = [i for i in range(len(Registers.NAMES)) if i not in (Registers.F, Registers.SP, Registers.PC)]
    first = "  ".join(f"{Registers.NAMES[i]} {registers[i]:02X}" for i in general)
    second = (f"PC {registers[Registers.PC]:04X}  SP {registers[Registers.SP]:04X}  "
              f"F {registers[Registers.F]:02X} {format_flags(registers[Registers.F])}")
    return first + "\n" + second
