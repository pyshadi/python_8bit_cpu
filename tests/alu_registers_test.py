from alu import ALU
from registers import Registers

def test_ALU_operations():

    alu = ALU()
    a = 0b11001100
    b = 0b00110011

    # Test ADD
    assert alu.add(a, b) == (a + b) & alu.mask

    # Test SUB
    assert alu.sub(a, b) == (a - b) & alu.mask

    # Test AND
    assert alu.and_(a, b) == a & b

    # Test OR
    assert alu.or_(a, b) == a | b

    # Test XOR
    assert alu.xor(a, b) == a ^ b

    # Test NOT
    assert alu.not_(a) == (~a) & alu.mask

    # Test shift left
    assert alu.shift_left(a) == (a << 1) & alu.mask

    # Test shift right
    assert alu.shift_right(a) == (a >> 1) & alu.mask

    # Test arithmetic shift right
    sign_bit = a & (1 << (alu.mask.bit_length() - 1))
    assert alu.arithmetic_shift_right(a) == ((a >> 1) & alu.mask) | sign_bit

    # Test rotate left
    msb = (a >> (alu.mask.bit_length() - 1)) & 1
    assert alu.rotate_left(a) == ((a << 1) & alu.mask) | msb

    # Test rotate right
    lsb = a & 1
    assert alu.rotate_right(a) == ((a >> 1) & alu.mask) | (lsb << (alu.mask.bit_length() - 1))


def test_registers():
    regs = Registers()

    # Test register storage
    for i in range(regs.num_registers):
        regs.registers[i] = i
        assert regs.registers[i] == i

    # Test register constants
    assert Registers.A == 0
    assert Registers.B == 1
    assert Registers.C == 2
    assert Registers.D == 3
    assert Registers.X == 4
    assert Registers.Y == 5
    assert Registers.SP == 6
    assert Registers.PC == 7


if __name__ == "__main__":
    test_ALU_operations()
    test_registers()
    print("All tests passed.")
