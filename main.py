from src.cpu import CPU
from src.memory import ROM, RAM
from src.assembler import Assembler

def test_cpu():

    source = '''
         mvi, A, 20     ; A = 20
         st, A, 25      ; RAM[25] = A
         ld, D, 25      ; D = RAM[25]
         addi, D, 10    ; D += 10
         st, D, 35      ; RAM[35] = D
         ld, E, 35      ; E = RAM[35]
         hlt
     '''
    code = Assembler.assemble(source)
    rom = ROM(len(code), code)
    ram = RAM(2048, bit_width=16)
    cpu = CPU(rom, ram, bit_width=8)

    while not cpu.halted:
        cpu.run()

    print("Register values:")
    for i, reg in enumerate(cpu.registers.registers):
        print(f"R{i}: {reg}")

if __name__ == "__main__":
    test_cpu()
