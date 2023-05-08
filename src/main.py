from cpu import CPU
from memory import ROM, RAM
from registers import Registers


def test_cpu():
    source = [
        0x04, 0x01,  # mvi a, 0x01
        0x05, 0x02,  # mvi b, 0x02
        0x06, 0x03,  # mvi c, 0x03
        0x07, 0x04,  # mvi d, 0x04
        0x10,  # add a, b
        0x11,  # add a, c
        0x12,  # add a, d
        0x0c, 0x10, # store a, (0x10)
        0x08, 0x10,  # load a, (0x10)
        0xff  # hlt
    ]



    rom = ROM(len(source), source)
    ram = RAM(512)
    cpu = CPU(rom, ram, bit_width=8)

    # Run the test program
    while not cpu.halted:
        cpu.run()


    print("Register values:")
    for i, reg in enumerate(cpu.registers.registers):
        print(f"R{i}: {reg}")
    print(cpu.ram.read(0x10))

if __name__ == "__main__":
    test_cpu()
