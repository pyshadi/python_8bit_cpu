import operator

from src.alu import Flags
from src.registers import Registers


class StackOverflowError(IndexError):
    pass


class StackUnderflowError(IndexError):
    pass


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
            0x2a: self.jae,
            0x2b: self.jb,
            0x2c: self.jbe,

            0x2d: self.push,
            0x2e: self.pushi,
            0x2f: self.pusha,
            0x30: self.pop,
            0x31: self.call,
            0x32: self.ret,

            0x33: self.inv,
            0x34: self.sar,

            0x35: self.out,
            0x36: self.outc,

            0xff: self.hlt,
        }

    def decode(self, opcode):
        if opcode in self.opcode_map:
            return self.opcode_map[opcode]
        else:
            raise NotImplementedError(f"Unknown opcode: {opcode}")

    # --- Operand helpers -------------------------------------------------------
    # Each reads an instruction's operands from ROM and returns
    # (register index, register value, second value).
    # Registers and immediates are 1 byte; addresses are 2 bytes (fetch_word).

    def _reg(self):
        reg = self.cpu.fetch_byte()
        return reg, self.cpu.registers.read(reg)

    def _reg_reg(self):
        reg, value = self._reg()
        return reg, value, self.cpu.registers.read(self.cpu.fetch_byte())

    def _reg_imm(self):
        reg, value = self._reg()
        return reg, value, self.cpu.fetch_byte()

    def _reg_mem(self):
        reg, value = self._reg()
        return reg, value, self.cpu.ram.read(self.cpu.fetch_word())

    # --- Stack and jump helpers ------------------------------------------------

    # The stack grows down from the top of RAM. SP starts at ram.size - 1 (empty)
    # and points at the most recently pushed byte.

    def _push(self, value):
        sp = self.cpu.registers.read(Registers.SP) - 1
        if sp < 0:
            raise StackOverflowError(f"stack overflow: RAM of size {self.cpu.ram.size} is full")
        self.cpu.ram.write(sp, value)
        self.cpu.registers.write(Registers.SP, sp)

    def _pop(self):
        sp = self.cpu.registers.read(Registers.SP)
        if sp >= self.cpu.ram.size - 1:
            raise StackUnderflowError("stack underflow: pop or ret on an empty stack")
        value = self.cpu.ram.read(sp)
        self.cpu.registers.write(Registers.SP, sp + 1)
        return value

    def _jump(self, address):
        self.cpu.registers.write(Registers.PC, address)

    def _jump_if_flag(self, flag, is_set):
        address = self.cpu.fetch_word()
        if bool(self.cpu.registers.read(Registers.F) & flag) == is_set:
            self._jump(address)

    def _jump_if_zero(self, is_zero):
        _, value = self._reg()
        address = self.cpu.fetch_word()
        if (value == 0) == is_zero:
            self._jump(address)

    def _jump_if_compare(self, compare):
        _, value, immediate = self._reg_imm()
        address = self.cpu.fetch_word()
        if compare(value, immediate):
            self._jump(address)

    def _write(self, reg, value):
        self.cpu.registers.write(reg, value)

    # --- Data transfer ---------------------------------------------------------

    def nop(self):
        """No operation."""

    def mov(self):
        """mov, D, S: copy register S into register D."""
        dest, _, value = self._reg_reg()
        self._write(dest, value)

    def mvi(self):
        """mvi, D, imm: load an immediate value into register D."""
        dest, _, value = self._reg_imm()
        self._write(dest, value)

    def ld(self):
        """ld, D, mem: load RAM[mem] into register D."""
        dest, _, value = self._reg_mem()
        self._write(dest, value)

    def st(self):
        """st, S, mem: store register S into RAM[mem]."""
        _, value = self._reg()
        self.cpu.ram.write(self.cpu.fetch_word(), value)

    # --- Arithmetic and logic --------------------------------------------------
    # reg, reg forms write the result to A; reg, imm and reg, mem forms write it
    # back to the register.

    def add(self):
        _, a, b = self._reg_reg()
        self._write(Registers.A, self.cpu.alu.add(a, b))

    def addi(self):
        reg, a, b = self._reg_imm()
        self._write(reg, self.cpu.alu.add(a, b))

    def adda(self):
        reg, a, b = self._reg_mem()
        self._write(reg, self.cpu.alu.add(a, b))

    def sub(self):
        _, a, b = self._reg_reg()
        self._write(Registers.A, self.cpu.alu.sub(a, b))

    def subi(self):
        reg, a, b = self._reg_imm()
        self._write(reg, self.cpu.alu.sub(a, b))

    def suba(self):
        reg, a, b = self._reg_mem()
        self._write(reg, self.cpu.alu.sub(a, b))

    def mul(self):
        _, a, b = self._reg_reg()
        self._write(Registers.A, self.cpu.alu.mul(a, b))

    def muli(self):
        reg, a, b = self._reg_imm()
        self._write(reg, self.cpu.alu.mul(a, b))

    def mula(self):
        reg, a, b = self._reg_mem()
        self._write(reg, self.cpu.alu.mul(a, b))

    def div(self):
        _, a, b = self._reg_reg()
        self._write(Registers.A, self.cpu.alu.div(a, b))

    def divi(self):
        reg, a, b = self._reg_imm()
        self._write(reg, self.cpu.alu.div(a, b))

    def diva(self):
        reg, a, b = self._reg_mem()
        self._write(reg, self.cpu.alu.div(a, b))

    def inc(self):
        reg, value = self._reg()
        self._write(reg, self.cpu.alu.add(value, 1))

    def dec(self):
        reg, value = self._reg()
        self._write(reg, self.cpu.alu.sub(value, 1))

    def andd(self):
        _, a, b = self._reg_reg()
        self._write(Registers.A, self.cpu.alu.and_(a, b))

    def andi(self):
        reg, a, b = self._reg_imm()
        self._write(reg, self.cpu.alu.and_(a, b))

    def anda(self):
        reg, a, b = self._reg_mem()
        self._write(reg, self.cpu.alu.and_(a, b))

    def ord(self):
        _, a, b = self._reg_reg()
        self._write(Registers.A, self.cpu.alu.or_(a, b))

    def ori(self):
        reg, a, b = self._reg_imm()
        self._write(reg, self.cpu.alu.or_(a, b))

    def ora(self):
        reg, a, b = self._reg_mem()
        self._write(reg, self.cpu.alu.or_(a, b))

    def xord(self):
        _, a, b = self._reg_reg()
        self._write(Registers.A, self.cpu.alu.xor(a, b))

    def xori(self):
        reg, a, b = self._reg_imm()
        self._write(reg, self.cpu.alu.xor(a, b))

    def xora(self):
        reg, a, b = self._reg_mem()
        self._write(reg, self.cpu.alu.xor(a, b))

    def rtl(self):
        reg, value = self._reg()
        self._write(reg, self.cpu.alu.rotate_left(value))

    def rtr(self):
        reg, value = self._reg()
        self._write(reg, self.cpu.alu.rotate_right(value))

    def shl(self):
        reg, value, n = self._reg_imm()
        self._write(reg, self.cpu.alu.shift_left(value, n))

    def shr(self):
        reg, value, n = self._reg_imm()
        self._write(reg, self.cpu.alu.shift_right(value, n))

    def inv(self):
        """inv, reg: bitwise NOT."""
        reg, value = self._reg()
        self._write(reg, self.cpu.alu.not_(value))

    def sar(self):
        """sar, reg: arithmetic shift right by one bit, keeping the sign bit."""
        reg, value = self._reg()
        self._write(reg, self.cpu.alu.arithmetic_shift_right(value))

    # --- Output ------------------------------------------------------------------

    def out(self):
        """out, reg: print the register's value as a decimal number on its own line."""
        _, value = self._reg()
        self.cpu.output.append(f"{value}\n")

    def outc(self):
        """outc, reg: print the register's value as a character (e.g. 72 prints H)."""
        _, value = self._reg()
        self.cpu.output.append(chr(value))

    # --- Compare (sets flags in F only) ------------------------------------------

    def cmp(self):
        _, a, b = self._reg_reg()
        self.cpu.alu.compare(a, b)

    def cmpi(self):
        _, a, b = self._reg_imm()
        self.cpu.alu.compare(a, b)

    def cmpa(self):
        _, a, b = self._reg_mem()
        self.cpu.alu.compare(a, b)

    # --- Jumps -------------------------------------------------------------------

    def jmp(self):
        """jmp, mem"""
        self._jump(self.cpu.fetch_word())

    def jc(self):
        """jc, mem: jump if carry is set."""
        self._jump_if_flag(Flags.CARRY, True)

    def jnc(self):
        """jnc, mem: jump if carry is clear."""
        self._jump_if_flag(Flags.CARRY, False)

    def jz(self):
        """jz, reg, mem: jump if the register is 0."""
        self._jump_if_zero(True)

    def jnz(self):
        """jnz, reg, mem: jump if the register is not 0."""
        self._jump_if_zero(False)

    def je(self):
        """je, reg, imm, mem: jump if reg == imm."""
        self._jump_if_compare(operator.eq)

    def ja(self):
        """ja, reg, imm, mem: jump if reg > imm."""
        self._jump_if_compare(operator.gt)

    def jae(self):
        """jae, reg, imm, mem: jump if reg >= imm."""
        self._jump_if_compare(operator.ge)

    def jb(self):
        """jb, reg, imm, mem: jump if reg < imm."""
        self._jump_if_compare(operator.lt)

    def jbe(self):
        """jbe, reg, imm, mem: jump if reg <= imm."""
        self._jump_if_compare(operator.le)

    # --- Stack and subroutines -----------------------------------------------------

    def push(self):
        """push, reg"""
        _, value = self._reg()
        self._push(value)

    def pushi(self):
        """pushi, imm"""
        self._push(self.cpu.fetch_byte())

    def pusha(self):
        """pusha, mem: push RAM[mem]."""
        self._push(self.cpu.ram.read(self.cpu.fetch_word()))

    def pop(self):
        """pop, reg"""
        reg = self.cpu.fetch_byte()
        self._write(reg, self._pop())

    def call(self):
        """call, mem: push the 16-bit return address (high byte, then low byte) and jump."""
        address = self.cpu.fetch_word()
        return_address = self.cpu.registers.read(Registers.PC)
        self._push(return_address >> 8)
        self._push(return_address & 0xFF)
        self._jump(address)

    def ret(self):
        """ret: pop the 16-bit return address (low byte, then high byte) and jump to it."""
        low_byte = self._pop()
        high_byte = self._pop()
        self._jump((high_byte << 8) | low_byte)

    def hlt(self):
        """Halt the CPU."""
        self.cpu.halted = True
