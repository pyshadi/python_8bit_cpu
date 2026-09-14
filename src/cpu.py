from src.registers import Registers
from src.decoder import Decoder
from src.alu import ALU


class CPU:
    def __init__(self, rom, ram, bit_width=8):
        self.rom = rom
        self.ram = ram
        self.registers = Registers()
        self.alu = ALU(bit_width, self.registers)
        self.decoder = Decoder(self)
        self.halted = False

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
