"""
A JSON command interface to the emulator, used by the Brassboard dashboard through Pyodide.

The page sends commands such as {"command": "step"} to Session.handle() and gets back
{"state": ..., "trace": [...], "stopped": bool, "clear_trace": bool} as JSON.
"""
import base64
import json
import re
from collections import deque

from src.assembler import Assembler, AssemblerError
from src.cpu import CPU
from src.disassembler import DisassemblerError, disassemble
from src.memory import ROM, RAM
from src.registers import Registers
from src.trace import StopReason, format_effect

TRACE_LIMIT = 200             # most recent entries kept for each trace view
RAM_SIZES = (1024, 4096, 65536)
_ASSEMBLER_LINE = re.compile(r"^line (\d+): (.*)$", re.DOTALL)


class Session:
    """
    One program and machine. Status is one of:
    empty (nothing loaded), ready (loaded, not started), paused, break, halted, error.
    """

    def __init__(self, ram_size=1024):
        self.ram_size = self._check_ram_size(ram_size)
        self.program = None
        self.cpu = None
        self.labels = {}
        self.requested_breakpoints = set()  # source lines, kept even while the source doesn't assemble
        self.status = "empty"
        self.error = None                   # {"line": int or None, "message": str}
        self.written = []                   # register names written by the last instruction
        self.last_ram_writes = []           # RAM addresses written by the last instruction
        self.return_cells = set()           # RAM addresses holding bytes pushed by call
        self._clear_recent()

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
        try:
            return json.dumps(handlers[name](**command))
        except (TypeError, ValueError) as e:
            return json.dumps({"error": str(e)})

    def load(self, source, breakpoints=(), ram_size=None):
        """
        Assemble source and power on a fresh machine with it. ram_size must be one of RAM_SIZES.
        """
        if ram_size is not None:
            self.ram_size = self._check_ram_size(ram_size)
        self._forget_run()
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
        self._record(record)
        self._remember_last(record)
        self.status = "halted" if record.halted else "paused"
        return self._result(stopped=record.halted)

    def run(self, max_steps=100_000, quiet=False):
        """
        Run up to max_steps instructions, stopping early at a breakpoint, hlt or an error.
        With quiet=True only {"stopped", "status"} is returned; the trace is kept for the next full result.
        """
        if not self._can_run():
            return self._quiet(True) if quiet else self._result(stopped=True)
        last = [None]
        current = [self.cpu.registers.read(Registers.PC)]

        def on_step(record):
            self._record(record)
            last[0] = record
            current[0] = record.next_address

        try:
            result = self.cpu.run_until(max_steps=max_steps, on_step=on_step)
        except Exception as e:
            self._runtime_error(current[0], e)
            return self._quiet(True) if quiet else self._result(stopped=True)

        if last[0] is not None:
            self._remember_last(last[0])
        self.status = {StopReason.HALTED: "halted", StopReason.BREAKPOINT: "break"}.get(result.reason, "paused")
        stopped = result.reason != StopReason.STEP_LIMIT
        return self._quiet(stopped) if quiet else self._result(stopped=stopped)

    def reset(self):
        if self.cpu is not None:
            self.cpu.reset()
            self.status, self.error = "ready", None
        self._forget_run()
        return self._result(clear_trace=True)

    # --- State -----------------------------------------------------------------

    def state(self):
        if self.cpu is not None:
            registers = list(self.cpu.registers.registers)
            cycles = self.cpu.cycles
            ram = bytes(self.cpu.ram.memory)
        else:
            registers = [0] * len(Registers.NAMES)
            registers[Registers.SP] = self.ram_size - 1
            cycles = 0
            ram = bytes(self.ram_size)

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
                "bytecode": base64.b64encode(bytes(self.program.bytecode)).decode("ascii"),
                "label_list": [[name, address] for name, address in
                               sorted(self.program.labels.items(), key=lambda item: (item[1], item[0]))],
            }

        sp = registers[Registers.SP]
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
            "memory": {
                "size": self.ram_size,
                "ram": base64.b64encode(ram).decode("ascii"),
                "return_cells": sorted(a for a in self.return_cells if a >= sp),
                "last_writes": self.last_ram_writes,
            },
        }

    # --- Helpers ---------------------------------------------------------------

    def _result(self, stopped=False, clear_trace=False):
        return {"state": self.state(), "trace": self._flush_trace(), "stopped": stopped, "clear_trace": clear_trace}

    def _quiet(self, stopped):
        return {"stopped": stopped, "status": self.status}

    def _can_run(self):
        return self.cpu is not None and self.status not in ("halted", "error")

    @staticmethod
    def _check_ram_size(ram_size):
        if ram_size not in RAM_SIZES:
            sizes = ", ".join(str(size) for size in RAM_SIZES)
            raise ValueError(f"RAM size must be one of {sizes} bytes, got {ram_size}")
        return ram_size

    def _clear_recent(self):
        self._recent = deque(maxlen=TRACE_LIMIT)        # every instruction
        self._recent_ram = deque(maxlen=TRACE_LIMIT)    # instructions that wrote RAM
        self._recent_jumps = deque(maxlen=TRACE_LIMIT)  # instructions that jumped

    def _forget_run(self):
        self.written, self.last_ram_writes, self.return_cells = [], [], set()
        self._clear_recent()

    def _record(self, record):
        self._recent.append(record)
        if record.ram_writes:
            self._recent_ram.append(record)
        if record.jumped:
            self._recent_jumps.append(record)
        if record.instruction.mnemonic == "call":
            self.return_cells.update(record.ram_writes)
        else:
            self.return_cells.difference_update(record.ram_writes)

    def _remember_last(self, record):
        self.written = [Registers.NAMES[reg] for reg in record.register_writes]
        self.last_ram_writes = list(record.ram_writes)

    def _flush_trace(self):
        """
        Entries recorded since the last result, oldest first. Each says which trace views it belongs to.
        """
        in_all = {record.cycle for record in self._recent}
        records = {record.cycle: record for record in (*self._recent_ram, *self._recent_jumps, *self._recent)}
        entries = [self._entry(records[cycle], cycle in in_all) for cycle in sorted(records)]
        self._clear_recent()
        return entries

    def _apply_breakpoints(self, lines):
        self.requested_breakpoints = {int(line) for line in lines}
        if self.cpu is not None:
            self.cpu.breakpoints = {self.program.line_addresses[line] for line in self._active_breakpoints()}

    def _active_breakpoints(self):
        """Requested breakpoint lines that hold an instruction (all of them while the source has errors)."""
        if self.program is None:
            return sorted(self.requested_breakpoints)
        return sorted(line for line in self.requested_breakpoints if line in self.program.line_addresses)

    def _entry(self, record, in_all):
        return {
            "cycle": record.cycle,
            "address": record.address,
            "bytes": list(record.instruction.bytes),
            "text": record.instruction.text(self.labels),
            "effect": format_effect(record, self.labels),
            "all": in_all,
            "ram": bool(record.ram_writes),
            "jump": record.jumped,
        }

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
