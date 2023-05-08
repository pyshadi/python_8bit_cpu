
class Registers:
    # Constants for register indices
    A, B, C, D, X, Y, SP, PC = range(8)

    def __init__(self, num_registers=8):
        self.registers = [0] * num_registers
        self.num_registers = num_registers

    def read(self, reg_num):
        return self.registers[reg_num]

    def write(self, reg_num, value):
        self.registers[reg_num] = value