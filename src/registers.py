class Registers:
    # Constants for register indices
    A, B, C, D, E, F, G, H, I, J, K, L, X, Y, SP, PC = range(16)
    NAMES = ("A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "X", "Y", "SP", "PC")

    DATA_MASK = 0xFF      # general purpose registers and flags are 8-bit
    ADDRESS_MASK = 0xFFFF  # SP and PC are 16-bit

    def __init__(self, num_registers=16):
        self.registers = [0] * num_registers
        self.num_registers = num_registers

    def _check_index(self, reg_num):
        if reg_num < 0 or reg_num >= self.num_registers:
            raise IndexError(f"Invalid register index: {reg_num}")

    def read(self, reg_num):
        self._check_index(reg_num)
        return self.registers[reg_num]

    def write(self, reg_num, value):
        self._check_index(reg_num)
        mask = self.ADDRESS_MASK if reg_num in (Registers.SP, Registers.PC) else self.DATA_MASK
        self.registers[reg_num] = value & mask
