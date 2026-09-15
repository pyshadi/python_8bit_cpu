"""
A JSON command interface to the emulator, used by the Brassboard dashboard through Pyodide.

The page sends commands such as {"command": "step"} to Session.handle() and gets back
{"state": ..., "trace": [...], "stopped": bool, "clear_trace": bool} as JSON.
"""
import json
import re
from collections import deque

from src.assembler import Assembler, AssemblerError
from src.cpu import CPU
from src.disassembler import DisassemblerError, disassemble
from src.memory import ROM, RAM
from src.registers import Registers
from src.trace import StopReason, format_effect

TRACE_LIMIT = 200  # most recent trace entries returned by one run command
_ASSEMBLER_LINE = re.compile(r"^line (\d+): (.*)$", re.DOTALL)


class Session:
    """
    One program and machine. Status is one of:
    empty (nothing loaded), ready (loaded, not started), paused, break, halted, error.
    """

    def __init__(self, ram_size=1024):
        self.ram_size = ram_size
        self.program = None
        self.cpu = None
        self.labels = {}
        self.requested_breakpoints = set()  # source lines, kept even while the source doesn't assemble
        self.status = "empty"
        self.error = None                   # {"line": int or None, "message": str}
        self.written = []                   # register names written by the last instruction

    # --- Commands --------------------------------------------------------------

    def handle(self, command_json):
        command = json.loads(command_json)
        name = command.pop("command", None)
        handlers = {
            "load": self.load,
            "set_breakpoints": self.set_breakpoints,
            "step": self.step,
            "run": self.run,
            "reset": self.reset,
            "state": self._result,
        }
        if name not in handlers:
            return json.dumps({"error": f"unknown command {name!r}"})
        return json.dumps(handlers[name](**command))

    def load(self, source, breakpoints=()):
        """
        Assemble source and power on a fresh machine with it.
        """
        self.written = []
        try:
            program = Assembler.assemble_program(source)
        except AssemblerError as e:
            self.program, self.cpu, self.labels = None, None, {}
            self.status, self.error = "error", self._assembler_error(str(e))
            self.requested_breakpoints = set(breakpoints)
            return self._result(clear_trace=True)

        self.program = program
        self.labels = {}
        for name, address in program.labels.items():
            self.labels.setdefault(address, name)
        code = program.bytecode
        self.cpu = CPU(ROM(max(len(code), 1), code), RAM(self.ram_size))
        self.status, self.error = "ready", None
        self._apply_breakpoints(breakpoints)
        return self._result(clear_trace=True)

    def set_breakpoints(self, lines):
        self._apply_breakpoints(lines)
        return self._result()

    def step(self):
        if not self._can_run():
            return self._result()
        address = self.cpu.registers.read(Registers.PC)
        try:
            record = self.cpu.step()
        except Exception as e:  # errors raised by the program itself
            self._runtime_error(address, e)
            return self._result(stopped=True)
        self.written = self._written_names(record)
        self.status = "halted" if record.halted else "paused"
        return self._result([self._entry(record)], stopped=record.halted)

    def run(self, max_steps=100_000):
        """
        Run up to max_steps instructions, stopping early at a breakpoint, hlt or an error.
        """
        if not self._can_run():
            return self._result(stopped=True)
        records = deque(maxlen=TRACE_LIMIT)
        current = [self.cpu.registers.read(Registers.PC)]

        def on_step(record):
            records.append(record)
            current[0] = record.next_address

        try:
            result = self.cpu.run_until(max_steps=max_steps, on_step=on_step)
        except Exception as e:
            self._runtime_error(current[0], e)
            return self._result([self._entry(r) for r in records], stopped=True)

        if records:
            self.written = self._written_names(records[-1])
        self.status = {StopReason.HALTED: "halted", StopReason.BREAKPOINT: "break"}.get(result.reason, "paused")
        return self._result([self._entry(r) for r in records], stopped=result.reason != StopReason.STEP_LIMIT)

    def reset(self):
        if self.cpu is not None:
            self.cpu.reset()
            self.status, self.error, self.written = "ready", None, []
        return self._result(clear_trace=True)

    # --- State -----------------------------------------------------------------

    def state(self):
        if self.cpu is not None:
            registers = list(self.cpu.registers.registers)
            cycles = self.cpu.cycles
        else:
            registers = [0] * len(Registers.NAMES)
            registers[Registers.SP] = self.ram_size - 1
            cycles = 0

        current_line, next_instruction = None, None
        if self.program is not None and self.status in ("ready", "paused", "break"):
            pc = registers[Registers.PC]
            current_line = self.program.address_lines.get(pc)
            try:
                instruction = disassemble(self.program.bytecode, pc)
                next_instruction = {"address": pc, "bytes": list(instruction.bytes), "text": instruction.text(self.labels)}
            except DisassemblerError:
                pass

        program = None
        if self.program is not None:
            program = {
                "size": len(self.program.bytecode),
                "labels": len(self.program.labels),
                "lines": [[line, address] for line, address in sorted(self.program.line_addresses.items())],
            }

        return {
            "status": self.status,
            "error": self.error,
            "registers": registers,
            "written": self.written,
            "cycles": cycles,
            "current_line": current_line,
            "next": next_instruction,
            "breakpoints": self._active_breakpoints(),
            "program": program,
        }

    # --- Helpers ---------------------------------------------------------------

    def _result(self, trace=None, stopped=False, clear_trace=False):
        return {"state": self.state(), "trace": trace or [], "stopped": stopped, "clear_trace": clear_trace}

    def _can_run(self):
        return self.cpu is not None and self.status not in ("halted", "error")

    def _apply_breakpoints(self, lines):
        self.requested_breakpoints = {int(line) for line in lines}
        if self.cpu is not None:
            self.cpu.breakpoints = {self.program.line_addresses[line] for line in self._active_breakpoints()}

    def _active_breakpoints(self):
        """Requested breakpoint lines that hold an instruction (all of them while the source has errors)."""
        if self.program is None:
            return sorted(self.requested_breakpoints)
        return sorted(line for line in self.requested_breakpoints if line in self.program.line_addresses)

    def _entry(self, record):
        return {
            "cycle": record.cycle,
            "address": record.address,
            "bytes": list(record.instruction.bytes),
            "text": record.instruction.text(self.labels),
            "effect": format_effect(record, self.labels),
        }

    @staticmethod
    def _written_names(record):
        return [Registers.NAMES[reg] for reg in record.register_writes]

    @staticmethod
    def _assembler_error(text):
        match = _ASSEMBLER_LINE.match(text)
        if match:
            return {"line": int(match.group(1)), "message": match.group(2)}
        return {"line": None, "message": text}

    def _runtime_error(self, address, error):
        self.status = "error"
        if address >= len(self.program.bytecode):
            self.error = {"line": None, "message": f"Ran past the end of the program at {address:04X}. Is a hlt missing?"}
        else:
            self.error = {"line": self.program.address_lines.get(address),
                          "message": f"{type(error).__name__} at {address:04X}: {error}"}
