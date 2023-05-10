from src.registers import Registers

class Decoder:
    def __init__(self, cpu):
        self.cpu = cpu
        self.opcode_map = {
            0x00: self.nop,
            0x01: self.mov,
            0x02: self.mvi,
            0x03: self.ld,
            0x04: self.st,

            0x05: self.add,
            0x06: self.addi,
            0x07: self.adda,
            0x08: self.sub,
            0x09: self.subi,
            0x0A: self.suba,
            0x0B: self.mul,
            0x0C: self.muli,
            0x0D: self.mula,
            0x0E: self.div,
            0x0F: self.divi,
            0x10: self.diva,
            0x11: self.inc,
            0x12: self.dec,

            0x13: self.andd,
            0x14: self.andi,
            0x15: self.anda,
            0x16: self.ord,
            0x17: self.ori,
            0x18: self.ora,
            0x19: self.xord,
            0x1a: self.xori,
            0x1b: self.xora,
            0x1c: self.rtl,
            0x1d: self.rtr,
            0x1e: self.shl,
            0x1f: self.shr,

            0x20: self.cmp,
            0x21: self.cmpi,
            0x22: self.cmpa,

            0x23: self.jmp,
            0x24: self.jc,
            0x25: self.jnc,
            0x26: self.je,
            0x27: self.jz,
            0x28: self.jnz,
            0x29: self.ja,
            0x30: self.jae,
            0x31: self.jb,
            0x32: self.jbe,

            0x33: self.push,
            0x34: self.pushi,
            0x35: self.pusha,
            0x36: self.pop,
            0x37: self.call,
            0x38: self.ret,

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
    def mov(self):
        dest = self.cpu.fetch_byte()
        source = self.cpu.fetch_byte()
        value = self.cpu.registers.read(source)
        self.cpu.registers.write(dest, value)
    def mvi(self):
        """
        Move an immediate value into the A register.
        """
        dest = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        self.cpu.registers.write(dest, value)
    def ld(self):
        """
        Load the value at the specified memory address into the accumulator.
        """
        dest = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        value = self.cpu.ram.read(address)
        print('DESTINATION in LOAD', dest)
        self.cpu.registers.write(dest, value)
    def st(self):
        """
        Store the value in the accumulator to the specified memory address.
        """
        source = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        value = self.cpu.registers.read(source)
        self.cpu.ram.write(address, value)
    def add(self):

        reg_1 = self.cpu.fetch_byte()
        reg_2 = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(reg_1)
        value_2 = self.cpu.registers.read(reg_2)
        result = self.cpu.alu.add(value_1, value_2)
        self.cpu.registers.write(Registers.A, result)
    def addi(self):
        dest  = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        value_at_dest = self.cpu.registers.read(dest)

        result = self.cpu.alu.add(value, value_at_dest)
        self.cpu.registers.write(dest, result)
    def adda(self):

        dest= self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        dest_value = self.cpu.registers.read(dest)
        address_value = self.cpu.ram.read(address)
        result = self.cpu.alu.add(dest_value, address_value)
        self.cpu.registers.write(dest, result)
    def sub(self):
        """
        Subtract the value in source register to dest Register.
        """
        reg_1 = self.cpu.fetch_byte()
        reg_2 = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(reg_1)
        value_2 = self.cpu.registers.read(reg_2)
        result = self.cpu.alu.sub(value_1, value_2)
        self.cpu.registers.write(Registers.A, result)
    def subi(self):
        """
        Subtract the value in the B register to the accumulator.
        """
        dest  = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        value_at_dest = self.cpu.registers.read(dest)

        result = self.cpu.alu.sub(value_at_dest, value)
        self.cpu.registers.write(dest, result)
    def suba(self):

        dest= self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        dest_value = self.cpu.registers.read(dest)
        address_value = self.cpu.ram.read(address)
        result = self.cpu.alu.sub(dest_value, address_value)
        self.cpu.registers.write(dest, result)
    def mul(self):

        reg_1 = self.cpu.fetch_byte()
        reg_2 = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(reg_1)
        value_2 = self.cpu.registers.read(reg_2)
        result = self.cpu.alu.mul(value_1, value_2)
        self.cpu.registers.write(Registers.A, result)
    def muli(self):
        dest  = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        value_at_dest = self.cpu.registers.read(dest)

        result = self.cpu.alu.mul(value, value_at_dest)
        self.cpu.registers.write(dest, result)
    def mula(self):

        dest= self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        dest_value = self.cpu.registers.read(dest)
        address_value = self.cpu.ram.read(address)
        result = self.cpu.alu.mul(dest_value, address_value)
        self.cpu.registers.write(dest, result)
    def div(self):

        reg_1 = self.cpu.fetch_byte()
        reg_2 = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(reg_1)
        value_2 = self.cpu.registers.read(reg_2)
        result = self.cpu.alu.mul(value_1, value_2)
        self.cpu.registers.write(Registers.A, result)
    def divi(self):
        dest  = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        value_at_dest = self.cpu.registers.read(dest)

        result = self.cpu.alu.mul(value, value_at_dest)
        self.cpu.registers.write(dest, result)
    def diva(self):

        dest= self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        dest_value = self.cpu.registers.read(dest)
        address_value = self.cpu.ram.read(address)
        result = self.cpu.alu.div(dest_value, address_value)
        self.cpu.registers.write(Registers.A, result)
    def inc(self):
        """
        Increment the value in the register by 1.
        """
        dest = self.cpu.fetch_byte()
        value = self.cpu.registers.read(dest) + 1
        self.cpu.registers.write(dest, value)
    def dec(self):
        """
        Decrement the value in the register by 1.
        """
        dest = self.cpu.fetch_byte()
        value = self.cpu.registers.read(dest) - 1
        self.cpu.registers.write(dest, value)

    def andd(self):
        """
        AND the value in the reg_1, reg_2 registers to the accumulator.
        """
        reg_1 = self.cpu.fetch_byte()
        reg_2 = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(reg_1)
        value_2 = self.cpu.registers.read(reg_2)
        result = self.cpu.alu.and_(value_1, value_2)
        self.cpu.registers.write(Registers.A, result)
    def andi(self):
        """
        AND the value in the reg_1, and num registers to the accumulator.
        """
        dest = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(dest)
        result = self.cpu.alu.and_(value_1, value)
        self.cpu.registers.write(dest, result)
    def anda(self):
        """
        AND the value in the reg, and value in address to the accumulator.
        """
        dest = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()

        dest_value = self.cpu.registers.read(dest)
        address_value = self.cpu.ram.read(address)
        result = self.cpu.alu.and_(dest_value, address_value)
        self.cpu.registers.write(dest, result)
    def ord(self):
        """
        OR the value in the reg_1, reg_2 registers to the accumulator.
        """
        reg_1 = self.cpu.fetch_byte()
        reg_2 = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(reg_1)
        value_2 = self.cpu.registers.read(reg_2)
        result = self.cpu.alu.or_(value_1, value_2)
        self.cpu.registers.write(Registers.A, result)
    def ori(self):
        """
        OR the value in the reg_1, value registers to the accumulator.
        """
        dest = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        dest_value = self.cpu.registers.read(dest)
        result = self.cpu.alu.or_(dest_value, value)
        self.cpu.registers.write(dest, result)
    def ora(self):
        """
        OR the value in the reg, and value in address to the accumulator.
        """
        dest = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()

        dest_value = self.cpu.registers.read(dest)
        address_value = self.cpu.ram.read(address)
        result = self.cpu.alu.or_(dest_value, address_value)
        self.cpu.registers.write(dest, result)
    def xord(self):
        """
        XOR the value in the reg_1, reg_2 registers to the accumulator.
        """
        reg_1 = self.cpu.fetch_byte()
        reg_2 = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(reg_1)
        value_2 = self.cpu.registers.read(reg_2)
        result = self.cpu.alu.xor_(value_1, value_2)
        self.cpu.registers.write(Registers.A, result)
    def xori(self):
        """
        XOR the value in the reg_1, value registers to the accumulator.
        """
        dest = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        dest_value = self.cpu.registers.read(dest)
        result = self.cpu.alu.xor_(dest_value, value)
        self.cpu.registers.write(dest, result)
    def xora(self):
        """
        XOR the value in the reg, and value in address to the accumulator.
        """
        dest = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()

        dest_value = self.cpu.registers.read(dest)
        address_value = self.cpu.ram.read(address)
        result = self.cpu.alu.xor_(dest_value, address_value)
        self.cpu.registers.write(dest, result)

    def rtl(self):
        """
        Rotate the value in the  register one bit to the left.
        """
        dest = self.cpu.fetch_byte()
        value = self.cpu.registers.read(dest)
        new_value = self.cpu.alu.rotate_left(value)
        self.cpu.registers.write(dest, new_value)
    def rtr(self):
        """
        Rotate the value in the  register one bit to the right.
        """
        dest = self.cpu.fetch_byte()
        value = self.cpu.registers.read(dest)
        new_value = self.cpu.alu.rotate_right(value)
        self.cpu.registers.write(dest, new_value)
    def shl(self):
        """
        Shift the value in the register n bits to the left.
        """
        dest = self.cpu.fetch_byte()
        shift_value = self.cpu.fetch_byte()
        dest_value = self.cpu.registers.read(dest)
        new_value = self.cpu.alu.shift_left(dest_value, shift_value )
        self.cpu.registers.write(dest, new_value)
    def shr(self):
        """
        Shift the value in the register n bits to the right.
        """
        dest = self.cpu.fetch_byte()
        shift_value = self.cpu.fetch_byte()
        dest_value = self.cpu.registers.read(dest)
        new_value = self.cpu.alu.shift_right(dest_value, shift_value )
        self.cpu.registers.write(dest, new_value)

    def cmp(self):
        """
        Compare the value in reg_1 with the value in reg_2.
        """
        reg_1 = self.cpu.fetch_byte()
        reg_2 = self.cpu.fetch_byte()
        value_1 = self.cpu.registers.read(reg_1)
        value_2 = self.cpu.registers.read(reg_2)

        zero_flag, carry_flag, overflow_flag, sign_flag=self.cpu.alu.compare(value_1, value_2 )
        new_value = (zero_flag << 3) | (carry_flag << 2) | (overflow_flag << 1) | sign_flag
        self.cpu.registers.write(Registers.F, new_value)
    def cmpi(self):
        """
        Compare the value in reg_1 with the value in reg_2.
        """
        reg = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        reg_value = self.cpu.registers.read(reg)

        zero_flag, carry_flag, overflow_flag, sign_flag=self.cpu.alu.compare(reg_value, value)
        new_value = (zero_flag << 3) | (carry_flag << 2) | (overflow_flag << 1) | sign_flag
        self.cpu.registers.write(Registers.F, new_value)
    def cmpa(self):
        """
        Compare the value in reg_1 with the value in reg_2.
        """
        reg = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        reg_value = self.cpu.registers.read(reg)
        address_value = self.cpu.ram.read(address)

        zero_flag, carry_flag, overflow_flag, sign_flag=self.cpu.alu.compare(reg_value, address_value)
        new_value = (zero_flag << 3) | (carry_flag << 2) | (overflow_flag << 1) | sign_flag
        self.cpu.registers.write(Registers.F, new_value)

    def jmp(self):
        """
        Jump to the specified address.
        """
        address = self.cpu.fetch_word()
        self.cpu.registers.write(Registers.PC, address)
    def jc(self):
        """
        Jump to the specified address if the carry flag is set.
        """
        address = self.cpu.fetch_byte()
        flags = self.cpu.registers.read(Registers.F)
        if (flags & 0b0100) != 0:  # Check if the carry flag is set
            self.cpu.registers.write(Registers.PC, address)
    def jnc(self):
        """
        Jump to the specified address if the carry flag is set.
        """
        address = self.cpu.fetch_byte()
        flags = self.cpu.registers.read(Registers.F)
        if (flags & 0b0100) == 0:  # Check if the carry flag is set
            self.cpu.registers.write(Registers.PC, address)
    def je(self):
        """
        Jump to the specified address if the value in the first register is equal the specified value.
        """
        address = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        if self.cpu.registers.read(self.cpu.registers.A) == value:
            self.cpu.registers.write(self.cpu.registers.PC, address)
    def jz(self):
        """
        Jump to the specified address if the value in the register is equal 0.
        """
        reg = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        if self.cpu.registers.read(reg) == 0:
            self.cpu.registers.write(self.cpu.registers.PC, address)

    def jnz(self):
        """
        Jump to the specified address if the value in the register is not equal 0.
        """
        reg = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        if self.cpu.registers.read(reg) != 0:
            self.cpu.registers.write(self.cpu.registers.PC, address)
    def ja(self):
        """
        Jump to the specified address if the value in the register is greater than the specified value.
        """
        reg = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        if self.cpu.registers.read(reg) > value:
            self.cpu.registers.write(reg, address)
    def jae(self):
        """
        Jump to the specified address if the value in the register is greater than or equal the specified value.
        """
        reg = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        if self.cpu.registers.read(reg) >= value:
            self.cpu.registers.write(reg, address)
    def jb(self):
        """
        Jump to the specified address if the value in the  register is greater than the specified value.
        """
        reg = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        if self.cpu.registers.read(reg) < value:
            self.cpu.registers.write(reg, address)
    def jbe(self):
        """
        Jump to the specified address if the value in the  register is greater than or equal the specified value.
        """
        reg = self.cpu.fetch_byte()
        value = self.cpu.fetch_byte()
        address = self.cpu.fetch_byte()
        if self.cpu.registers.read(reg) <= value:
            self.cpu.registers.write(reg, address)

    def push(self):
        """
        Push a register value onto the stack.
        """

        reg = self.cpu.fetch_byte()
        reg_value = self.cpu.registers.read(reg)
        sp_value= self.cpu.registers.read(Registers.SP)
        sp_value -= 1  # Decrement the stack pointer
        self.cpu.ram.write(sp_value, reg_value)
        self.cpu.registers.write(Registers.SP, sp_value)  # Decrement the stack pointer

    def pushi(self):
        """
        Push a value onto the stack.
        """

        value = self.cpu.fetch_byte()
        sp_value= self.cpu.registers.read(Registers.SP)
        sp_value -= 1  # Decrement the stack pointer
        self.cpu.ram.write(sp_value, value)
        self.cpu.registers.write(Registers.SP, sp_value)  # Decrement the stack pointer

    # def pusha(self):
    #     """
    #     Push an address value onto the stack.
    #     """
    #     address = self.cpu.fetch_byte()
    #     ram_value = self.cpu.ram.read(address)
    #     sp_value= self.cpu.registers.read(Registers.SP)
    #     sp_value -= 1  # Decrement the stack pointer
    #     self.cpu.ram.write(sp_value, ram_value)

    def pusha(self):
        """
        Push an address value onto the stack.
        """
        address = self.cpu.fetch_byte()
        ram_value = self.cpu.ram.read(address)
        sp_value = self.cpu.registers.read(Registers.SP)
        sp_value -= 1  # Decrement the stack pointer
        if sp_value >= 0:
            self.cpu.ram.write(sp_value, ram_value)

        else:
            raise IndexError(f"Stack pointer out of bounds: {sp_value}")

        self.cpu.registers.write(Registers.SP, sp_value)

    def pop(self):
        """
        Pop a value off the stack.
        """
        value = self.cpu.ram.read(self.cpu.registers.read(Registers.SP))
        self.cpu.registers.write(Registers.A, value)
        sp_value = self.cpu.registers.read(Registers.SP)
        sp_value += 1  # Increment the stack pointer
        self.cpu.registers.write(Registers.SP, sp_value)

    def call(self):
        # Get the address to jump to
        address = self.cpu.fetch()

        # Push the return address onto the stack
        return_address = self.cpu.registers.read(Registers.PC)
        sp_value = self.cpu.registers.read(Registers.SP)
        sp_value -= 1  # Decrement the stack pointer by 1
        if sp_value >= 0:
            self.cpu.ram.write(sp_value, return_address)
        else:
            raise IndexError(f"Stack pointer out of bounds: {sp_value}")
        self.cpu.registers.write(Registers.SP, sp_value)

        # Jump to the function address
        # Jump to the function address (write low byte to PC register)
        self.cpu.registers.write(Registers.PC, address)


    def ret(self):
        """
        Return from a function call.
        """
        # Pop the return address from the stack
        sp_value = self.cpu.registers.read(Registers.SP)
        return_address = self.cpu.ram.read(sp_value)
        sp_value += 1  # Increment the stack pointer by 2 for a word
        self.cpu.registers.write(Registers.SP, sp_value)

        print('return_address', return_address)
        # Jump to the return address
        self.cpu.registers.write(Registers.PC, return_address)


    def hlt(self):
        """
        Halt the CPU.
        """
        self.cpu.halted = True