from src.registers import Registers
from src.decoder import Decoder
from src.alu import ALU
from src.disassembler import DisassemblerError, disassemble
from src.trace import RunResult, Snapshot, StepRecord, StopReason


class CPU:
    def __init__(self, rom, ram, bit_width=8):
        self.rom = rom
        self.ram = ram
        self.registers = Registers()
        self.alu = ALU(bit_width, self.registers)
        self.decoder = Decoder(self)
        self.halted = False
        self.cycles = 0           # instructions executed since creation or the last reset
        self.breakpoints = set()  # addresses where run_until stops before executing
        self.output = []          # text printed by out/outc, one string per printing instruction

        self.registers.write(Registers.SP, self.ram.size - 1)

    def fetch_word(self):
        # Fetch a 16-bit value as two consecutive 8-bit values from memory
        low_byte = self.fetch()
        high_byte = self.fetch()
        # Combine the low and high bytes into a single 16-bit value
        return (high_byte << 8) | low_byte

    def fetch_byte(self):
        # Fetch an 8-bit value from memory
        return self.fetch()

    def fetch(self):
        pc = self.registers.read(Registers.PC)
        opcode = self.rom.read(pc)
        self.registers.write(Registers.PC, pc+1)
        return opcode

    def decode(self, opcode):
        return self.decoder.decode(opcode)

    def execute(self, instruction):
        instruction()

    def run(self):
        """
        Run one fetch-decode-execute cycle. Call repeatedly until `halted` is True.
        """
        opcode = self.fetch()
        instruction = self.decoder.decode(opcode)
        self.execute(instruction)
        self.cycles += 1

    # --- Debugging -------------------------------------------------------------

    def step(self):
        """
        Run one instruction and return a StepRecord describing what it did.
        """
        if self.halted:
            raise RuntimeError("the CPU is halted; call reset() to run again")
        address = self.registers.read(Registers.PC)
        try:
            instruction = disassemble(self.rom.memory, address)
        except DisassemblerError:
            self.run()  # raises the decoder's own error for the bad instruction
            raise

        register_log, ram_log = {}, {}
        output_count = len(self.output)
        self.registers.write_log, self.ram.write_log = register_log, ram_log
        try:
            self.run()
        except Exception:
            # Instructions are all-or-nothing: put back anything written before the error.
            for reg, old in register_log.items():
                self.registers.registers[reg] = old
            for addr, old in ram_log.items():
                self.ram.memory[addr] = old
            del self.output[output_count:]
            raise
        finally:
            self.registers.write_log = self.ram.write_log = None

        return StepRecord(
            cycle=self.cycles,
            address=address,
            instruction=instruction,
            register_writes={reg: (old, self.registers.registers[reg])
                             for reg, old in sorted(register_log.items()) if reg != Registers.PC},
            ram_writes={addr: (old, self.ram.memory[addr]) for addr, old in sorted(ram_log.items())},
            next_address=self.registers.read(Registers.PC),
            halted=self.halted,
            output="".join(self.output[output_count:]),
        )

    def undo(self, record):
        """
        Reverse the most recent step() that has not been undone yet, using the old values in its record.
        """
        for reg, (old, _) in record.register_writes.items():
            self.registers.registers[reg] = old
        for address, (old, _) in record.ram_writes.items():
            self.ram.memory[address] = old
        self.registers.registers[Registers.PC] = record.address
        self.halted = False
        self.cycles -= 1
        if record.output:
            self.output.pop()

    def run_until(self, max_steps=100_000, on_step=None):
        """
        Step until the CPU halts, reaches a breakpoint, or has executed max_steps instructions.
        on_step, if given, is called with each StepRecord.

        A breakpoint stops execution before its instruction runs. The instruction a run starts
        on always executes, so calling run_until again continues past the breakpoint.
        """
        steps = 0
        while not self.halted:
            if steps and self.registers.read(Registers.PC) in self.breakpoints:
                return RunResult(StopReason.BREAKPOINT, steps)
            if steps >= max_steps:
                return RunResult(StopReason.STEP_LIMIT, steps)
            record = self.step()
            steps += 1
            if on_step is not None:
                on_step(record)
        return RunResult(StopReason.HALTED, steps)

    def snapshot(self):
        """
        Capture registers, RAM, halt state and cycle count.
        """
        return Snapshot(tuple(self.registers.registers), tuple(self.ram.memory), self.halted, self.cycles,
                        tuple(self.output))

    def restore(self, snapshot):
        """
        Return to a state captured by snapshot(). Breakpoints are not affected.
        """
        if len(snapshot.ram) != self.ram.size:
            raise ValueError(f"snapshot has {len(snapshot.ram)} bytes of RAM, but this CPU has {self.ram.size}")
        self.registers.registers[:] = snapshot.registers
        self.ram.memory[:] = snapshot.ram
        self.halted = snapshot.halted
        self.cycles = snapshot.cycles
        self.output[:] = snapshot.output

    def reset(self):
        """
        Clear registers and RAM, set PC to 0 and SP to the top of RAM. Breakpoints are kept.
        """
        self.registers.registers[:] = [0] * self.registers.num_registers
        self.ram.memory[:] = [0] * self.ram.size
        self.registers.write(Registers.SP, self.ram.size - 1)
        self.halted = False
        self.cycles = 0
        self.output.clear()
