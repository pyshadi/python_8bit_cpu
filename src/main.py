from cpu import CPU
from memory import ROM, RAM
from assembler import Assembler

def test_cpu():
    source = [
        0x02, 0, 1000,       # Move immediate value 2 into A
        0x04, 0x00, 0x10,
        0x12, 0x00,
        0x28, 0x00, 0x06,
        0xff,                      # Halt the program#
    ]

    source = '''
         mvi, A, 1000,
         loop:,
         dec, A,
         jnz, A, loop,
         hlt,
     '''
    code = Assembler.assemble(source)
    rom = ROM(len(code), code)
    ram = RAM(64, bit_width=8)
    cpu = CPU(rom, ram, bit_width=8)

    while not cpu.halted:
        cpu.run()

    print("Register values:")
    for i, reg in enumerate(cpu.registers.registers):
        print(f"R{i}: {reg}")

    # print(cpu.ram.read(0x10))

if __name__ == "__main__":
    test_cpu()
