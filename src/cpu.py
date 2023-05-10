from registers import Registers
from decoder import Decoder


class ALU:
    def __init__(self, bit_width=8):
        self.mask = (1 << bit_width) - 1

    def add(self, a, b):
        return (a + b) & self.mask

    def sub(self, a, b):
        return (a - b) & self.mask

    def mul(self, a, b):
        return (a * b) & self.mask
    def div(self, a, b):
        if b !=0:
            return (a / b) & self.mask
        else:
            return (0 & self.mask)

    def and_(self, a, b):
        return a & b

    def or_(self, a, b):
        return a | b

    def xor(self, a, b):
        return a ^ b

    def not_(self, a):
        return (~a) & self.mask

    def shift_left(self, a, n):
        return (a << n) & self.mask

    def shift_right(self, a, n):
        return (a >> n) & self.mask

    def arithmetic_shift_right(self, a):
        sign_bit = a & (1 << (self.mask.bit_length() - 1))
        return ((a >> 1) & self.mask) | sign_bit

    def rotate_left(self, a):
        msb = (a >> (self.mask.bit_length() - 1)) & 1
        return ((a << 1) & self.mask) | msb

    def rotate_right(self, a):
        lsb = a & 1
        return ((a >> 1) & self.mask) | (lsb << (self.mask.bit_length() - 1))

    def compare(self, a, b):
        result = (a - b) & self.mask
        zero_flag = result == 0
        carry_flag = a < b
        overflow_flag = ((a ^ b) & (a ^ result) & (1 << (self.mask.bit_length() - 1))) != 0
        sign_flag = (result & (1 << (self.mask.bit_length() - 1))) != 0
        return zero_flag, carry_flag, overflow_flag, sign_flag



class CPU:
    def __init__(self, rom, ram, bit_width=8):
        self.rom = rom
        self.ram = ram
        self.registers = Registers()
        self.alu = ALU(bit_width)
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

    def fetch_address(self):
        """
        Fetch a 8-bit address from RAM.
        """
        pc = self.registers.read(Registers.PC)
        address = self.ram.read(pc)
        self.registers.write(Registers.PC, pc+1)
        return address
    def fetch(self):
        pc = self.registers.read(Registers.PC)
        # print('pc in fetch', pc)
        # print('sp in fetch', self.registers.read(Registers.SP))
        opcode = self.rom.read(pc)
        self.registers.write(Registers.PC, pc+1)
        return opcode

    def decode(self, opcode):
        return self.decoder.decode(opcode)

    def execute(self, instruction):
        instruction()


    def run(self):
        pc = self.registers.registers[Registers.PC]
        opcode = self.fetch()
        #print(f"Executing opcode: {opcode:02x} at address: {pc:02x}")  # Add this line
        instruction = self.decoder.decode(opcode)
        self.execute(instruction)
