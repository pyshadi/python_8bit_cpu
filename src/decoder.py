from registers import Registers

class Decoder:
    def __init__(self, cpu):
        self.cpu = cpu
        self.opcode_map = {
            0x00: self.nop,
            0x01: self.mv_b_a,
            0x02: self.mv_c_a,
            0x03: self.mv_d_a,

            0x04: self.mvi_a,
            0x05: self.mvi_b,
            0x06: self.mvi_c,
            0x07: self.mvi_d,

            0x08: self.load_a,
            0x09: self.load_b,
            0x0a: self.load_c,
            0x0b: self.load_d,

            0x0c: self.store_a,
            0x0d: self.store_b,
            0x0e: self.store_c,
            0x0f: self.store_d,

            0x10: self.add_a_b,
            0x11: self.add_a_c,
            0x12: self.add_a_d,

            0x13: self.sub_a_b,
            0x14: self.sub_a_c,
            0x15: self.sub_a_d,

            0x16: self.inc_a,
            0x17: self.inc_b,
            0x18: self.inc_c,
            0x19: self.inc_d,

            0x1a: self.dec_a,
            0x1b: self.dec_b,
            0x1c: self.dec_c,
            0x1d: self.dec_d,

            0x1e: self.and_a_b,
            0x1f: self.and_a_c,
            0x20: self.and_a_d,

            0x21: self.sub_a_b,
            0x22: self.sub_a_c,
            0x23: self.sub_a_d,

            0x24: self.and_a_b,
            0x25: self.and_a_c,
            0x26: self.and_a_d,

            0x27: self.or_a_b,
            0x28: self.or_a_c,
            0x29: self.or_a_d,

            0x2a: self.xor_a_b,
            0x2b: self.xor_a_c,
            0x2c: self.xor_a_d,

            0x2d: self.rotate_l_a,
            0x2e: self.rotate_r_a,

            0x2f: self.cmp_a_b,
            0x30: self.cmp_a_c,
            0x31: self.cmp_a_d,

            0x32: self.jmp,
            0x33: self.push,
            0x34: self.pop,
            0x35: self.jmp_greater_than,
            0xff: self.hlt,



            # Add more instructions here
        }

    def decode(self, opcode):
        if opcode in self.opcode_map:
            return self.opcode_map[opcode]
        else:
            raise NotImplementedError(f"Unknown opcode: {opcode}")


    def nop(self):
        """
        No operation.
        """
        pass

    def mv_b_a(self):
        """
        Move B value into the A register.
        """
        value_B = self.cpu.registers.read(Registers.B)
        self.cpu.registers.write(Registers.A, value_B)
    def mv_c_a(self):
        """
        Move C value into the A register.
        """
        value_C = self.cpu.registers.read(Registers.C)
        self.cpu.registers.write(Registers.A, value_C)
    def mv_d_a(self):
        """
        Move D value into the A register.
        """
        value_D = self.cpu.registers.read(Registers.D)
        self.cpu.registers.write(Registers.A, value_D)

 ## Move immediate value
    def mvi_a(self):
        """
        Move an immediate value into the A register.
        """
        value = self.cpu.fetch_byte()
        self.cpu.registers.write(Registers.A, value)
    def mvi_b(self):
        """
        Move an immediate value into the B register.
        """
        value = self.cpu.fetch_byte()

        self.cpu.registers.write(Registers.B, value)
    def mvi_c(self):
        """
        Move an immediate value into the C register.
        """
        value = self.cpu.fetch_byte()
        self.cpu.registers.write(Registers.C, value)
    def mvi_d(self):
        """
        Move an immediate value into the D register.
        """
        value = self.cpu.fetch_byte()
        self.cpu.registers.write(Registers.D, value)

## load from memory address
    def load_a(self):
        """
        Load the value at the specified memory address into the accumulator.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.ram.read(address)
        self.cpu.registers.write(Registers.A, value)
    def load_b(self):
        """
        Load the value at the specified memory address into the B.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.ram.read(address)
        self.cpu.registers.write(Registers.B, value)
    def load_c(self):
        """
        Load the value at the specified memory address into the C.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.ram.read(address)
        self.cpu.registers.write(Registers.C, value)
    def load_d(self):
        """
        Load the value at the specified memory address into the D.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.ram.read(address)
        self.cpu.registers.write(Registers.D, value)

## store to memory address
    def store_a(self):
        """
        Store the value in the accumulator to the specified memory address.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.registers.read(Registers.A)
        self.cpu.ram.write(address, value)
    def store_b(self):
        """
        Store the value in the B register to the specified memory address.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.registers.read(Registers.B)
        self.cpu.ram.write(address, value)
    def store_c(self):
        """
        Store the value in the C register to the specified memory address.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.registers.read(Registers.C)
        self.cpu.ram.write(address, value)
    def store_d(self):
        """
        Store the value in the D register to the specified memory address.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.registers.read(Registers.D)
        self.cpu.ram.write(address, value)

    def add_a_b(self):
        """
        Add the value in the B register to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_B = self.cpu.registers.read(Registers.B)
        result = self.cpu.alu.add(value_A, value_B)
        self.cpu.registers.write(Registers.A, result)
    def add_a_c(self):
        """
        Add the value in the C register to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_C = self.cpu.registers.read(Registers.C)
        result = self.cpu.alu.add(value_A, value_C)
        self.cpu.registers.write(Registers.A, result)
    def add_a_d(self):
        """
        Add the value in the D register to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_D = self.cpu.registers.read(Registers.D)
        result = self.cpu.alu.add(value_A, value_D)
        self.cpu.registers.write(Registers.A, result)

    def sub_a_b(self):
        """
        Subtract the value in the B register to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_B = self.cpu.registers.read(Registers.B)
        result = self.cpu.alu.sub(value_A, value_B)
        self.cpu.registers.write(Registers.A, result)
    def sub_a_c(self):
        """
        Subtract the value in the C register from the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_C = self.cpu.registers.read(Registers.C)
        result = self.cpu.alu.sub(value_A, value_C)
        self.cpu.registers.write(Registers.A, result)
    def sub_a_d(self):
        """
        Subtract the value in the D register to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_D = self.cpu.registers.read(Registers.D)
        result = self.cpu.alu.sub(value_A, value_D)
        self.cpu.registers.write(Registers.A, result)

    def inc_a(self):
        """
        Increment the value in the A register by 1.
        """
        value = self.cpu.registers.read(Registers.A)
        self.cpu.registers.write(Registers.A, value)
    def inc_b(self):
        """
        Increment the value in the B register by 1.
        """
        value = self.cpu.registers.read(Registers.B)+ 1
        self.cpu.registers.write(Registers.B, value)
    def inc_c(self):
        """
        Increment the value in the C register by 1.
        """
        value = self.cpu.registers.read(Registers.C) + 1
        self.cpu.registers.write(Registers.C, value)
    def inc_d(self):
        """
        Increment the value in the D register by 1.
        """
        value = self.cpu.registers.read(Registers.D) + 1
        self.cpu.registers.write(Registers.D, value)

    def dec_a(self):
        """
        Decrement the value in the A register by 1.
        """
        value = self.cpu.registers.read(Registers.A) - 1
        self.cpu.registers.write(Registers.A, value)
    def dec_b(self):
        """
        Decrement the value in the B register by 1.
        """
        value = self.cpu.registers.B - 1
        self.cpu.registers.write(Registers.B, value)
    def dec_c(self):
        """
        Decrement the value in the C register by 1.
        """
        value = self.cpu.registers.read(Registers.C) - 1
        self.cpu.registers.write(Registers.C, value)
    def dec_d(self):
        """
        Decrement the value in the D register by 1.
        """
        value = self.cpu.registers.read(Registers.D) - 1
        self.cpu.registers.write(Registers.D, value)

    def and_a_b(self):
        """
        AND the value in the A, B registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_B = self.cpu.registers.read(Registers.B)
        result = self.cpu.alu.and_(value_A, value_B)
        self.cpu.registers.write(Registers.A, result)
    def and_a_c(self):
        """
        AND the value in the A, C registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_C = self.cpu.registers.read(Registers.C)
        result = self.cpu.alu.and_(value_A, value_C)
        self.cpu.registers.write(Registers.A, result)
    def and_a_d(self):
        """
        AND the value in the A, D registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_D = self.cpu.registers.read(Registers.D)
        result = self.cpu.alu.and_(value_A, value_D)
        self.cpu.registers.write(Registers.A, result)

    def or_a_b(self):
        """
        OR the value in the A, B registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_B = self.cpu.registers.read(Registers.B)
        result = self.cpu.alu.or_(value_A, value_B)
        self.cpu.registers.write(Registers.A, result)
    def or_a_c(self):
        """
        OR the value in the A, C registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_C = self.cpu.registers.read(Registers.C)
        result = self.cpu.alu.or_(value_A, value_C)
        self.cpu.registers.write(Registers.A, result)
    def or_a_d(self):
        """
        OR the value in the A, D registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_D = self.cpu.registers.read(Registers.D)
        result = self.cpu.alu.or_(value_A, value_D)
        self.cpu.registers.write(Registers.A, result)

    def xor_a_b(self):
        """
        xOR the value in the A, B registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_B = self.cpu.registers.read(Registers.B)
        result = self.cpu.alu.xor_(value_A, value_B)
        self.cpu.registers.write(Registers.A, result)
    def xor_a_c(self):
        """
        xOR the value in the A, C registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_C = self.cpu.registers.read(Registers.C)
        result = self.cpu.alu.xor_(value_A, value_C)
        self.cpu.registers.write(Registers.A, result)
    def xor_a_d(self):
        """
        xOR the value in the A, D registers to the accumulator.
        """
        value_A = self.cpu.registers.read(Registers.A)
        value_D = self.cpu.registers.read(Registers.D)
        result = self.cpu.alu.xor_(value_A, value_D)
        self.cpu.registers.write(Registers.A, result)

    def rotate_l_a(self):
        """
        Rotate the value in the A register one bit to the left.
        """
        value = self.cpu.registers.read(Registers.A)
        new_value = self.cpu.alu.rotate_left(value)
        self.cpu.registers.write(Registers.A, new_value)
    def rotate_r_a(self):
        """
        Rotate the value in the A register one bit to the right.
        """
        value = self.cpu.registers.read(Registers.A)
        new_value = self.cpu.alu.rotate_right(value)
        self.cpu.registers.write(Registers.A, new_value)

    def cmp_a_b(self):
        """
        Compare the value in the A register with the value in the B register.
        """
        self.cpu.alu.compare(self.cpu.registers.read(Registers.A), self.cpu.registers.read(Registers.B))
    def cmp_a_c(self):
        """
        Compare the value in the A register with the value in the C register.
        """
        self.cpu.alu.compare(self.cpu.registers.read(Registers.A), self.cpu.registers.read(Registers.C))
    def cmp_a_d(self):
        """
        Compare the value in the A register with the value in the D register.
        """
        self.cpu.alu.compare(self.cpu.registers.read(Registers.A), self.cpu.registers.read(Registers.D))

    def jmp(self):
        """
        Jump to the specified address.
        """
        address = self.cpu.fetch_word()
        self.cpu.registers.write(Registers.PC, address)
    def push(self):
        """
        Push a value onto the stack.
        """
        value = self.cpu.fetch_byte()
        value -= 1
        self.cpu.ram.write(self.cpu.registers.SP, value)

    def pop(self):
        """
        Pop a value off the stack.
        """
        value = self.cpu.ram.read(self.cpu.registers.SP)
        value += 1
        self.cpu.registers.write(Registers.A, value)

    def jmp_greater_than(self):
        """
        Jump to the specified address if the value in the first register is greater than the specified value.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        if self.cpu.registers.read(self.cpu.registers.A) > value:
            self.cpu.registers.write(self.cpu.registers.PC, address)

    def hlt(self):
        """
        Halt the CPU.
        """
        self.cpu.halted = True