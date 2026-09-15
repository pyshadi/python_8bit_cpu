from dataclasses import dataclass
from typing import Dict, Tuple

from src.disassembler import Instruction


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
