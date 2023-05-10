from src.alu import ALU
import src

alu = ALU()
#
# Test addition
assert alu.add(5, 10) == 15
assert alu.add(255, 2) == 1  # Overflow, should wrap around to 0
assert alu.flags == 0x02  # Carry flag should be set
#
# # Test subtraction
from src.alu import ALU

alu = ALU()

# Test addition
assert alu.add(5, 10) == 15  # 5 + 10 should equal 15
assert alu.add(255, 2) == 1  # 255 + 2 equals 257, but since our ALU can only handle 8 bits, it overflows and wraps around to 1
assert alu.flags == 0x02  # The addition resulted in an overflow, so the carry flag should be set

# Test subtraction
assert alu.sub(10, 5) == 5  # 10 - 5 should equal 5
assert alu.sub(5, 10) == 251  # 5 - 10 equals -5, but since our ALU can only handle 8 bits, it underflows and wraps around to 251
assert alu.flags == 0x02  # The subtraction resulted in an underflow, so the carry flag should be set

# Test multiplication
assert alu.mul(5, 10) == 50  # 5 * 10 should equal 50
assert alu.mul(128, 3) == 128  # 128 * 3 equals 384, but since our ALU can only handle 8 bits, it overflows and wraps around to 128
assert alu.flags == 0x02  # The multiplication resulted in an overflow, so the carry flag should be set

# Test division
assert alu.div(10, 5) == 2  # 10 / 5 should equal 2

# Test bitwise AND
assert alu.and_(0b1100, 0b1010) == 0b1000  # The bitwise AND of 1100 and 1010 should equal 1000

# Test bitwise OR
assert alu.or_(0b1100, 0b1010) == 0b1110  # The bitwise OR of 1100 and 1010 should equal 1110

# Test bitwise XOR
assert alu.xor(0b1100, 0b1010) == 0b0110  # The bitwise XOR of 1100 and 1010 should equal 0110

# Test bitwise NOT
assert alu.not_(0b00000001) == 0b11111110  # The bitwise NOT of 00000001 should equal 11111110

# Test left shift
assert alu.shift_left(0b01100000, 2) == 0b10000000  # Shifting 01100000 left by 2 bits should result in 10000000
assert alu.flags == 0x02  # The shift resulted in an overflow, so the carry flag should be set

# Test right shift
assert alu.shift_right(0b1100, 2) == 0b0011  # Shifting 1100 right by 2 bits should result in 0011

# Test arithmetic right shift
assert alu.arithmetic_shift_right(0b10000000) == 0b11000000  # Shifting 10000000 right by 1 bit should result in 11000000, with sign extension
assert alu.arithmetic_shift_right(0b00001111) == 0b00000111  # Shifting 00001111 right by 1 bit should result in 00000111, with sign extension
assert alu.arithmetic_shift_right(0b00001010) == 0b00000101
#
# Test rotate left
assert alu.rotate_left(0b10001100) == 0b00011001
assert alu.flags == 0x02  # Carry flag should be set

# Test rotate right
assert alu.rotate_right(0b1100) == 0b0110
assert alu.flags == 0x00  # Carry flag should be clear

# Test comparison
assert alu.compare(5, 10) == (False, True, False, True)  # 5 < 10, so carry and sign flags should be set
assert alu.compare(10, 5) == (False, False, False, False)  # 10 > 5, so no flags should be set
assert alu.compare(255, 1) == (False, False, False, True)
assert alu.compare(255, 255) == (True, False,  False, False)
