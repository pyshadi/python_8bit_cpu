# python_8bit_cpu

This is a simple (in progress) CPU simulator, which mimics the behavior of a computer's CPU. <br><br><br>
![UML Diagram](assets/img.png "UML-Code Structure")
<br>

## alu.py

The ALU class provides arithmetic and logical operations for the CPU. It supports operations like addition, subtraction, multiplication, division, bitwise AND, bitwise OR, bitwise XOR, bitwise NOT, left and right shifts, rotations, as well as comparison operations.<br>
Results are masked to the bit width (8 bits by default). Each operation updates the flags, whose bits are defined in the <code>Flags</code> class:

| Flag | Bit |
| --- | --- |
| <code>Flags.ZERO</code> | 0x01 |
| <code>Flags.CARRY</code> | 0x02 |
| <code>Flags.OVERFLOW</code> | 0x04 |
| <code>Flags.SIGN</code> | 0x08 |

When the ALU belongs to a CPU, the flags are stored in the <code>F</code> register, so conditional jumps such as <code>jc</code> see the result of the last arithmetic or compare operation. A standalone <code>ALU()</code> keeps them in its own <code>flags</code> attribute.<br>

## cpu.py

The CPU class takes a ROM object as input. The object contains the instructions that the CPU will execute, and a RAM object, which represents the computer's memory (including the stack). <br>
It has a set of Registers, which hold data that the CPU needs to perform its operations and it has an ALU object and a Decoder object that it uses to execute instructions.<br>

The CPU class has a <code>fetch</code> method, which fetches the next byte from ROM and advances PC. It also has a decode method, which decodes the byte into an instruction function. <br>
It has an execute method, which executes the instruction returned by the decode method.<br>

The <code>run</code> method performs a single fetch-decode-execute cycle. Call it in a loop until the CPU's <code>halted</code> attribute becomes True, which the "hlt" instruction sets:

<pre>
while not cpu.halted:
    cpu.run()
</pre>

A <code>fetch_byte</code> method fetches the next byte from ROM, and a <code>fetch_word</code> method fetches the next two bytes and combines them into a single 16-bit value.<br>

## registers.py

The Registers class has a <code>read</code> method, which takes a register index and returns the value stored in that register. It also has a write method, which takes a register index and a value, and stores that value in the specified register. Invalid indices raise an <code>IndexError</code>.<br>
It defines constants for register indices: <code>A, B, C, D, E, F, G, H, I, J, K, L, X, Y, SP,</code> and <code>PC</code>. These constants can be used in place of raw register indices to make the code more readable.<br>

<code>F</code> is the flags register and is overwritten by every ALU operation, so don't use it for general-purpose storage.<br>
General-purpose registers and <code>F</code> are 8-bit; <code>SP</code> and <code>PC</code> are 16-bit. Written values wrap around, so decrementing 0 gives 255.<br>

The Registers class has a registers attribute, which is a list of register values. It also has a <code>num_registers</code> attribute, which indicates the number of registers in the set. <br>
By default, the Registers class initializes with sixteen registers.<br>

## memory.py

### ROM
The ROM contains the instructions that the CPU will execute. It takes as input a <code>size</code> parameter, which represents the size of the ROM in bytes, and an optional <code>content</code> parameter, which is a list of bytes representing the initial contents of the ROM.<br>

The ROM class has a <code>read</code> method, which reads a byte from memory at the specified address. It also has a <code>write</code> method, which raises a RuntimeError because ROM is read-only.<br><br>

### RAM
The RAM class takes as input a <code>size</code> parameter, which represents the size of the RAM in bytes, and an optional <code>bit_width</code> parameter.<br>
The <code>read</code> method reads a byte from memory at the specified address. It also has a write method, which writes a byte to memory at the specified address.<br>
The RAM class also has <code>read_word</code> and <code>write_word</code> methods, which are used to read and write 16-bit words to memory. These methods are useful for working with data types that are larger than a single byte.<br>
The stack lives at the top of RAM: <code>SP</code> starts at <code>size - 1</code> and grows downwards.<br>

## decoder.py
The Decoder class is responsible for decoding the opcodes fetched from memory and executing them. Each instruction is a method on the Decoder, which reads its operands from ROM and uses the CPU's registers, RAM and ALU.<br>

It has an <code>opcode_map</code> dictionary attribute, which maps opcode values to their corresponding instruction methods. The dictionary includes entries for all the supported instructions, such as MOV, ADD, SUB, CMP, JMP, PUSH, POP, and HLT.<br>

The decode method takes an opcode value as input and returns the corresponding instruction method. If the opcode value is not found in the <code>opcode_map</code> dictionary, it raises a NotImplementedError.<br>


## assembler.py

The Assembler class has an <code>instructions</code> dictionary that maps each mnemonic to its opcode and number of operands, for example <code>mvi</code> (move immediate value) is opcode 0x02 with 2 operands. <code>opcode_map</code> is derived from it.<br>
The class also has a <code>register_map</code> dictionary that maps the names of the CPU's registers to their indices. For example, the register A is index 0x00.<br>
The assemble method takes in the assembly source code as input and returns the corresponding bytecode that can be executed by the CPU. It uses a two-pass process to translate the assembly code to bytecode.<br>

In the first pass, the method records the address of every label. A label is a name followed by a colon, either on its own line (<code>loop:</code>) or in front of an instruction (<code>loop: dec, A</code>).<br>

In the second pass, the method translates each instruction into its opcode followed by one byte per operand. An operand can be a register name, a label, or a number.<br>

Syntax rules:
- Instruction, operands, and labels are separated by commas.
- <code>;</code> starts a comment, either on its own line or after an instruction.
- Mnemonics and register names are case-insensitive.
- Numbers can be decimal, hex (<code>0x10</code>), binary (<code>0b101</code>) or octal (<code>0o17</code>), and must fit in a byte (0–255).

The assembler raises an <code>AssemblerError</code> (a <code>ValueError</code>) with the line number for:
- unknown instructions
- wrong operand counts
- invalid or out-of-range operands
- duplicate labels
- labels named like registers

Finally, the method returns the bytecode list, which can be loaded into the computer's memory and executed by the CPU.<br>

## Instruction Set

All addresses (<code>mem</code>) are one byte.

| Mnemonic | Opcode | Operands | Description |
| --- | --- | --- | --- |
| NOP | 0x00 | None | No operation |

### Data Transfer Instructions
| Mnemonic | Opcode | Operands | Description |
| --- | --- | --- | --- |
| MOV | 0x01 | D, S | Move data from Source register to Destination register |
| MVI | 0x02 | D, imm | Move immediate data into Destination register |
| LD | 0x03 | D, mem | Load data from memory into Destination register |
| ST | 0x04 | S, mem | Store data from Source register into memory |

### Arithmetic and Logical Instructions
| Mnemonic | Opcode | Operands | Description |
| --- | --- | --- | --- |
| ADD | 0x05 | reg, reg | Add data from a register to another and put result in the accumulator|
| ADDI | 0x06 |  D, imm | Add immediate data to  Destination register |
| ADDA | 0x07 | D, mem | Add data from memory to  Destination register |
| SUB | 0x08 | reg, reg | Subtract data in the second register from the first and put result in the accumulator |
| SUBI | 0x09 | D, imm | Subtract immediate data from  Destination register |
| SUBA | 0x0A | D, mem | Subtract memory data from  Destination register |
| MUL | 0x0B | reg, reg | Multiply data in a register with another and put result in the accumulator |
| MULI | 0x0C | D, imm | Multiply Destination register with immediate data |
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
| RTL | 0x1C | D | Rotate Destination register left |
| RTR | 0x1D | D | Rotate Destination register right |
| SHL | 0x1E | D, imm | Shift Destination register left by imm bits |
| SHR | 0x1F | D, imm | Shift Destination register right by imm bits |

### Control Transfer Instructions
| Mnemonic | Opcode | Operands | Description |
| --- | --- | --- | --- |
| CMP | 0x20 | reg, reg| Compare data in two registers and set the flags |
| CMPI | 0x21 | reg, imm | Compare the register with immediate data and set the flags |
| CMPA | 0x22 | reg, mem | Compare the register with memory data and set the flags |
| JMP | 0x23 | mem | Jump to a memory location |
| JC | 0x24 | mem | Jump to a memory location if the carry flag is set |
| JNC | 0x25 | mem | Jump to a memory location if the carry flag is not set |
| JE | 0x26 | reg, imm, mem | Jump to a memory location if register data is equal to immediate value |
| JZ | 0x27 | reg, mem | Jump to a memory location if register data is zero |
| JNZ | 0x28 | reg, mem | Jump to a memory location if register data is not zero |
| JA | 0x29 | reg, imm, mem | Jump to a memory location if register data is greater than immediate value |
| JAE | 0x30 | reg, imm, mem | Jump to a memory location if register data is greater than or equal to immediate value |
| JB | 0x31 | reg, imm, mem | Jump to a memory location if register data is smaller than immediate value |
| JBE | 0x32 | reg, imm, mem | Jump to a memory location if register data is smaller than or equal to immediate value |
| PUSH | 0x33 | reg | Push data from a register onto the stack |
| PUSHI | 0x34 | imm | Push immediate data onto the stack |
| PUSHA | 0x35 | mem | Push data from a memory location onto the stack |
| POP | 0x36 | reg | Pop data from the stack into a register |
| CALL | 0x37 | mem | Call a subroutine at a memory location |
| RET | 0x38 | None | Return from a subroutine |
| HLT | 0xFF | None | Halt the CPU |

## Example assembly program:
<pre>
mvi, A, 10      ; counter
loop:
dec, A
jnz, A, loop    ; repeat until A is 0
hlt
</pre>

## Testing

### main.py
From parent directory run main as module: <code>python3 -m main</code> or run it as a script: <code>python3 main.py</code>
The test_cpu function assembles a small program that stores a value in RAM, loads it back into another register, adds to it, and halts. After the program finishes running, the function prints out the values of the CPU's registers.<br>

### Unit tests
From parent directory run the test suite with pytest: <code>python3 -m pytest</code>

| File | Covers |
| --- | --- |
| <code>tests/alu_test.py</code> | ALU arithmetic, bitwise, shift, rotation and compare operations, including flags and edge cases |
| <code>tests/registers_test.py</code> | Register widths, wrap-around, and flags in the F register |
| <code>tests/instructions_test.py</code> | Instruction behavior: jumps, stack, call/ret, XOR and DIV |
| <code>tests/assembler_test.py</code> | Assembler syntax, labels, comments, and error handling |
| <code>tests/cpu_test.py</code> | End-to-end programs |
