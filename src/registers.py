class Registers:
    # Constants for register indices
    A, B, C, D, E, F, G, H, I, J, K, L, X, Y, SP, PC = range(16)

    def __init__(self, num_registers=16):
        self.registers = [0] * num_registers
        self.num_registers = num_registers

    def read(self, reg_num):
        if reg_num < 0 or reg_num >= self.num_registers:
            raise IndexError(f"Invalid register index: {reg_num}")
        return self.registers[reg_num]

    def write(self, reg_num, value):
        self.registers[reg_num] = value
