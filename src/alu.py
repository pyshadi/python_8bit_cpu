class ALU:
    def __init__(self, bit_width=8):
        self.mask = (1 << bit_width) - 1
        self.flags = 0
    def set_flag(self, flag):
        self.flags |= flag
    def clear_flag(self, flag):
        self.flags &= ~flag

    def add(self, a, b):
        result = a + b
        overflow_flag = (result & (1 << self.mask.bit_length())) != 0
        result &= self.mask
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        if overflow_flag:
            self.set_flag(0x02)  # set carry flag
        return result

    def sub(self, a, b):
        result = a - b
        borrow_flag = result < 0
        result &= self.mask
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        if borrow_flag:
            self.set_flag(0x02)  # set carry flag
        return result

    def mul(self, a, b):
        result = a * b
        overflow_flag = (result & (1 << self.mask.bit_length())) != 0
        result &= self.mask
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        if overflow_flag:
            self.set_flag(0x02)  # set carry flag
        return result
    def div(self, a, b):
        if b != 0:
            # Use Python's integer division to handle both signed and unsigned division
            result = int(a) // int(b)
            self.clear_flag(0x01)  # clear zero flag
            if result == 0:
                self.set_flag(0x01)  # set zero flag
            return result & self.mask
        else:
            raise ZeroDivisionError("attempt to divide by zero")

    def and_(self, a, b):
        result = a & b
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        return result
    def or_(self, a, b):
        result = a | b
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        return result
    def xor(self, a, b):
        result = a ^ b
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        return result
    def not_(self, a):
        result = (~a) & self.mask
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        return result
    def shift_left(self, a, n):
        result = (a << n) & self.mask
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        if a & (1 << (self.mask.bit_length() - n)):
            self.set_flag(0x02)  # set carry flag
        return result
    def shift_right(self, a, n):
        result = a >> n
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        return result & self.mask

    def arithmetic_shift_right(self, a):
        sign_bit = a & (1 << (self.mask.bit_length() - 1))
        result = ((a >> 1) & self.mask) | sign_bit
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        if sign_bit != 0:
            self.set_flag(0x02)  # set carry flag
        return result

    def rotate_left(self, a):
        msb = (a >> (self.mask.bit_length() - 1)) & 1
        result = ((a << 1) & self.mask) | msb
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        if msb:
            self.set_flag(0x02)  # set carry flag
        return result
    def rotate_right(self, a):
        lsb = a & 1
        result = ((a >> 1) & self.mask) | (lsb << (self.mask.bit_length() - 1))
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        if result == 0:
            self.set_flag(0x01)  # set zero flag
        if lsb:
            self.set_flag(0x02)  # set carry flag
        return result

    def compare(self, a, b):
        result = (a - b) & self.mask
        zero_flag = result == 0
        carry_flag = a < b
        overflow_flag = ((a ^ b) & (a ^ result) & (1 << (self.mask.bit_length() - 1))) != 0
        sign_flag = (result & (1 << (self.mask.bit_length() - 1))) != 0
        self.clear_flag(0x01)  # clear zero flag
        self.clear_flag(0x02)  # clear carry flag
        self.clear_flag(0x04)  # clear overflow flag
        self.clear_flag(0x08)  # clear sign flag
        if zero_flag:
            self.set_flag(0x01)  # set zero flag
        if carry_flag:
            self.set_flag(0x02)  # set carry flag
        if overflow_flag:
            self.set_flag(0x04)  # set overflow flag
        if sign_flag:
            self.set_flag(0x08)  # set sign flag
        return zero_flag, carry_flag, overflow_flag, sign_flag

