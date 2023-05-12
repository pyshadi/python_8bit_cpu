import pytest
from src.alu import ALU


def test_addition():
    alu = ALU()
    assert alu.add(5, 10) == 15
    assert alu.add(255, 2) == 1
    assert alu.flags == 0x02


def test_subtraction():
    alu = ALU()
    assert alu.sub(10, 5) == 5
    assert alu.sub(5, 10) == 251
    assert alu.flags == 0x02


def test_multiplication():
    alu = ALU()
    assert alu.mul(5, 10) == 50
    assert alu.mul(128, 3) == 128
    assert alu.flags == 0x02


def test_division():
    alu = ALU()
    assert alu.div(10, 5) == 2


def test_bitwise_operations():
    alu = ALU()
    assert alu.and_(0b1100, 0b1010) == 0b1000
    assert alu.or_(0b1100, 0b1010) == 0b1110
    assert alu.xor(0b1100, 0b1010) == 0b0110
    assert alu.not_(0b00000001) == 0b11111110


def test_shift_operations():
    alu = ALU()
    assert alu.shift_left(0b01100000, 2) == 0b10000000
    assert alu.flags == 0x02
    assert alu.shift_right(0b1100, 2) == 0b0011
    assert alu.arithmetic_shift_right(0b10000000) == 0b11000000
    assert alu.arithmetic_shift_right(0b00001111) == 0b00000111
    assert alu.arithmetic_shift_right(0b00001010) == 0b00000101


def test_rotation_operations():
    alu = ALU()
    assert alu.rotate_left(0b10001100) == 0b00011001
    assert alu.flags == 0x02
    assert alu.rotate_right(0b1100) == 0b0110
    assert alu.flags == 0x00


def test_comparison():
    alu = ALU()
    assert alu.compare(5, 10) == (False, True, False, True)
    assert alu.compare(10, 5) == (False, False, False, False)
    assert alu.compare(255, 1) == (False, False, False, True)
    assert alu.compare(255, 255) == (True, False, False, False)
