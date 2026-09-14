import pytest

from src.assembler import Assembler, AssemblerError
from src.registers import Registers
from tests.helpers import run_program


def test_basic_encoding():
    assert Assembler.assemble("mvi, A, 20\nhlt") == [0x02, 0x00, 20, 0xff]


def test_addresses_are_two_bytes_little_endian():
    assert Assembler.assemble("ld, A, 0x1234") == [0x03, 0x00, 0x34, 0x12]
    assert Assembler.assemble("jmp, 5") == [0x23, 5, 0]


def test_label_only_line_with_trailing_comma():
    assert Assembler.assemble("mvi, A, 10,\nloop:,\ndec, A,\njnz, A, loop,\nhlt,") == \
        [0x02, 0, 10, 0x12, 0, 0x28, 0, 3, 0, 0xff]


def test_comment_lines_do_not_shift_labels():
    source = "; a comment, with commas: and a colon\njmp, end\nmvi, C, 99\nend:\nhlt"
    assert Assembler.assemble(source) == [0x23, 6, 0, 0x02, 2, 99, 0xff]
    assert run_program(source).registers.read(Registers.C) == 0


def test_inline_comments():
    assert Assembler.assemble("mvi, A, 1 ; load one\nhlt ; stop") == [0x02, 0, 1, 0xff]


def test_label_on_same_line_as_instruction():
    source = "start: mvi, A, 3\nloop: dec, A\njnz, A, loop\nhlt"
    assert Assembler.assemble(source) == [0x02, 0, 3, 0x12, 0, 0x28, 0, 3, 0, 0xff]
    assert run_program(source).registers.read(Registers.A) == 0


def test_label_above_255():
    code = Assembler.assemble("jmp, end\n" + "nop\n" * 300 + "end:\nhlt")
    assert code[:3] == [0x23, 0x2F, 0x01]  # end = 3 + 300 = 0x12F


def test_mnemonics_and_registers_are_case_insensitive():
    assert Assembler.assemble("MVI, a, 5\nHLT") == [0x02, 0, 5, 0xff]


def test_hex_and_binary_literals():
    assert Assembler.assemble("mvi, A, 0x10\nmvi, B, 0b101") == [0x02, 0, 16, 0x02, 1, 5]


def test_unknown_instruction_raises():
    with pytest.raises(AssemblerError, match="line 2: unknown instruction 'mvx'"):
        Assembler.assemble("nop\nmvx, A, 5")


def test_wrong_operand_count_raises():
    with pytest.raises(AssemblerError, match="'mvi' takes 2 operand"):
        Assembler.assemble("mvi, A")


def test_invalid_operand_raises():
    with pytest.raises(AssemblerError, match="invalid operand 'nowhere'"):
        Assembler.assemble("jmp, nowhere")


def test_register_expected_raises():
    with pytest.raises(AssemblerError, match="expected a register, got '5'"):
        Assembler.assemble("inc, 5")


def test_register_where_value_expected_raises():
    with pytest.raises(AssemblerError, match="expected a number or label, got register 'B'"):
        Assembler.assemble("mvi, A, B")


def test_immediate_out_of_byte_range_raises():
    with pytest.raises(AssemblerError, match="does not fit in a byte"):
        Assembler.assemble("mvi, A, 1000")


def test_address_out_of_16_bit_range_raises():
    with pytest.raises(AssemblerError, match="does not fit in 16 bits"):
        Assembler.assemble("jmp, 0x10000")


def test_duplicate_label_raises():
    with pytest.raises(AssemblerError, match="duplicate label"):
        Assembler.assemble("a1:\nnop\na1:\nhlt")


def test_opcode_table_matches_decoder():
    decoder_map = run_program("hlt").decoder.opcode_map
    assert {opcode: decoder_map[opcode].__name__ for opcode in decoder_map} == \
        {opcode: mnemonic for mnemonic, opcode in Assembler.opcode_map.items()}


def test_opcodes_have_no_gaps():
    opcodes = sorted(opcode for opcode in Assembler.opcode_map.values() if opcode != 0xff)
    assert opcodes == list(range(len(opcodes)))


def test_label_named_like_register_raises():
    with pytest.raises(AssemblerError, match="register name"):
        Assembler.assemble("sp:\nhlt")
