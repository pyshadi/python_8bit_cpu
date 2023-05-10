from src.cpu import CPU
from src.memory import ROM, RAM
from src.assembler import Assembler

def test_cpu():

    source = [
        0x02, 0, 1000,       # Move immediate value 2 into A
        0x04, 0x00, 0x10,
        0x12, 0x00,
        0x28, 0x00, 0x06,
        0xff,                      # Halt the program#
    ]

    source = '''
         mvi, A, 20,
         st, A, 25,
         ld, D, 25,
         addi, D, 10,
         st, D, 35
         ld, E, 35
         hlt,
     '''
    code = Assembler.assemble(source)
    rom = ROM(2*len(code), code)
    ram = RAM(2048, bit_width=16)
    cpu = CPU(rom, ram, bit_width=8)

    while not cpu.halted:
        cpu.run()

    print("Register values:")
    for i, reg in enumerate(cpu.registers.registers):
        print(f"R{i}: {reg}")

    # print(cpu.ram.read(0x10))

if __name__ == "__main__":
    test_cpu()
