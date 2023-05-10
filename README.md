# python_8bit_cpu

This is a simple CPU simulator, which emulates the behavior of a computer's CPU. <br>
The CPU is programmed with a specific set of instructions that it can execute, and it fetches those instructions from memory as it runs.<br>

The repo has the following components:<br>

## cpu.py

### ALU
The ALU (Arithmetic Logic Unit) class provides arithmetic and logical operations for the CPU. It supports operations like addition, subtraction, multiplication, division, bitwise AND, bitwise OR, bitwise XOR, bitwise NOT, left and right shifts, as well as comparison operations.<br>

### CPU
The CPU class takes as input a ROM object, which contains the instructions that the CPU will execute, and a RAM object, which represents the computer's memory. It has a set of Registers, which hold data that the CPU needs to perform its operations and it has an ALU object and a Decoder object that it uses to execute instructions.<br>

The CPU class has a fetch method, which fetches the next instruction from memory and returns it as a byte. It also has a decode method, which decodes the byte into an instruction function. It has an execute method, which executes the instruction returned by the decode method.<br>

The run method fetches the next instruction, decodes it, and executes it. The run method loops until it encounters a "halt" instruction or until the halted attribute of the CPU object is set to True.<br>

The CPU class has a halted attribute, which is set to False by default. When the CPU encounters a "halt" instruction, it sets the halted attribute to True, which causes the run method to stop looping.<br>
A fetch_word method, which fetches the next two bytes from memory and combines them into a single 16-bit value.<br>
A fetch_byte method, which fetches the next byte from memory.<br>
A fetch_address method, which fetches the next byte from memory and returns it as an 8-bit address.<br>

## registers.py

Registers are used to store data that the CPU needs to perform its operations, such as the program counter and the accumulator.<br>

The Registers class has a read method, which takes a register index and returns the value stored in that register. It also has a write method, which takes a register index and a value, and stores that value in the specified register.<br>
It defines several constants for register indices, including A, B, C, D, E, F, X, Y, SP, and PC. These constants can be used in place of raw register indices to make the code more readable.<br>

The Registers class has a registers attribute, which is a list of register values. It also has a num_registers attribute, which indicates the number of registers in the set. By default, the Registers class initializes with ten registers, but this can be customized by passing a different value to the num_registers parameter when creating an instance of the class.<br>

## memory.py

### ROM
The ROM contains the instructions that the CPU will execute. It takes as input a size parameter, which represents the size of the ROM in bytes, and an optional content parameter, which is a list of bytes representing the initial contents of the ROM.<br>

The ROM class has a read method, which reads a byte from memory at the specified address. It also has a write method, which raises a RuntimeError because ROM is read-only.<br><br>

### RAM
The RAM class is used to store data that the CPU needs to perform its operations. It takes as input a size parameter, which represents the size of the RAM in bytes, and an optional bit_width parameter, which specifies the number of bits used to represent each byte in memory.<br>
The read method reads a byte from memory at the specified address. It also has a write method, which writes a byte to memory at the specified address.<br>
The RAM class also has read_word and write_word methods, which are used to read and write 16-bit words to memory. These methods are useful for working with data types that are larger than a single byte.<br>

## decoder.py
The Decoder class is responsible for decoding the opcodes fetched from memory and calling the appropriate instruction function from the ALU class based on the decoded opcode.<br>

It has an opcode_map dictionary attribute, which maps opcode values to their corresponding instruction functions in the ALU class. The dictionary includes entries for all the supported instructions, such as MOV, ADD, SUB, CMP, JMP, PUSH, POP, and HLT.<br>

The decode method takes an opcode value as input and returns the corresponding instruction function from the ALU class. If the opcode value is not found in the opcode_map dictionary, it raises a NotImplementedError.<br>


## assemblyer.py

The Assembler class is responsible for translating human-readable assembly code into machine code that can be executed by the CPU. It has a dictionary opcode_map that maps the assembly instructions to their corresponding opcodes in machine code. For example, the assembly instruction mvi (move immediate value) is mapped to the opcode 0x02.<br>
The class also has a register_map dictionary that maps the names of the CPU's registers to their corresponding addresses in memory. For example, the register A is mapped to the address 0x00.<br>
The assemble method takes in the assembly source code as input and returns the corresponding bytecode that can be executed by the CPU. It uses a two-pass process to translate the assembly code to bytecode.<br>

In the first pass, the method identifies any labels in the code and adds them to a dictionary labels. A label is identified as any line that ends with a colon :. The index of the label is then added to the dictionary.<br>

In the second pass, the method translates each line of assembly code into bytecode. It separates any labels from the instruction and splits the line into parts. It then translates the opcode using the opcode_map dictionary and appends it to the bytecode list. The method then translates any operands using the register_map dictionary or the labels dictionary if they are a label. If the operand is a number, it is simply appended to the bytecode list.<br>

Finally, the method returns the bytecode list, which can be loaded into the computer's memory and executed by the CPU.<br>

## Instruction Set

| Mnemonic | Opcode | Operands | Description |
| --- | --- | --- | --- |
| NOP | 0x00 | None | No operation |
| MOV | 0x01 | D, S | Move data from one Source register to Destination register |
| MVI | 0x02 | D, imm | Move immediate data into Destination register |
| LD | 0x03 | D, mem | Load data from memory into Destination register |
| ST | 0x04 | S, mem | Store data from Source register into memory |
| ADD | 0x05 | reg, reg | Add data from a register to another and put result in the accumulator|
| ADDI | 0x06 |  D, imm | Add immediate data to  Destination register |
| ADDA | 0x07 | D, mem | Add data from memory to  Destination register |
| SUB | 0x08 | reg, reg | Subtract data in a register from another and put result in the accumulator |
| SUBI | 0x09 | D, imm | Subtract immediate data from  Destination register |
| SUBA | 0x0A | D, mem | Subtract memory data from  Destination register |
| MUL | 0x0B | reg, reg | Multiply data in a register with another |
| MULI | 0x0C | D, imm | Multiply immediate data with register and put result in the accumulator |
| MULA | 0x0D | D, mem | Multiply memory data with data in Destination register |
| DIV | 0x0E | reg, reg| Divide a register by data in another register and put result in the accumulator |
| DIVI | 0x0F | D, imm | Divide Destination register by immediate data |
| DIVA | 0x10 | D, mem | Divide Destination register by data in memory |
| INC | 0x11 | D | Increment the value of Destination register |
| DEC | 0x12 | D | Decrement the value of Destination register |
| ANDD | 0x13 | reg, reg | Bitwise AND a register with data from another register and put result in the accumulator |
| ANDI | 0x14 | D, imm | Bitwise AND the register with immediate data |
| ANDA | 0x15 | D, mem | Bitwise AND the register with data from memory |
| ORD | 0x16 | reg, reg| Bitwise OR a register with data from another register and put result in the accumulator |
| ORI | 0x17 | D, imm | Bitwise OR Destination register with immediate data |
| ORA | 0x18 | D, mem | Bitwise OR Destination register with data from memory |
| XORD | 0x19 | reg, reg | Bitwise XOR a register with data from another register and put result in the accumulator |
| XORI | 0x1A | D, imm | Bitwise XOR Destination register with immediate data |
| XORA | 0x1B | D, mem | Bitwise XOR Destination register with data from memory |
| RTL | 0x1C | D | Rotate Destination register left|
| RTR | 0x1D | D | Rotate Destination register right|

## Testing
The test_cpu function sets up a simple test program and runs it on the simulated CPU. The program counts down from 10 and then halts. After the program finishes running, the function prints out the values of the CPU's registers and the contents of memory address 0x10.<br>
