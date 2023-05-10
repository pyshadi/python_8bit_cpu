# python_8bit_cpu

The provided code is an example of a simple CPU simulator, which emulates the behavior of a computer's central processing unit. <br>
The CPU is programmed with a specific set of instructions that it can execute, and it fetches those instructions from memory as it runs.<br>

The code consists of the following components:<br>

## cpu.py

### ALU
The ALU (Arithmetic Logic Unit) class provides arithmetic and logical operations for the CPU. It supports operations like addition, subtraction, multiplication, division, bitwise AND, bitwise OR, bitwise XOR, bitwise NOT, left and right shifts, as well as comparison operations.<br>

### CPU
The CPU class represents the central processing unit of the simulated computer. It takes as input a ROM object, which contains the instructions that the CPU will execute, and a RAM object, which represents the computer's memory. The CPU class also has a set of Registers, which hold data that the CPU needs to perform its operations. The CPU class has an ALU object and a Decoder object that it uses to execute instructions.<br>

The CPU class has a fetch method, which fetches the next instruction from memory and returns it as a byte. It also has a decode method, which decodes the byte into an instruction function. The CPU class has an execute method, which executes the instruction returned by the decode method.<br>

The CPU class has a run method, which fetches the next instruction, decodes it, and executes it. The run method loops until it encounters a "halt" instruction or until the halted attribute of the CPU object is set to True.<br>

The CPU class has a halted attribute, which is set to False by default. When the CPU encounters a "halt" instruction, it sets the halted attribute to True, which causes the run method to stop looping.<br>
The CPU class has a fetch_word method, which fetches the next two bytes from memory and combines them into a single 16-bit value.<br>
The CPU class has a fetch_byte method, which fetches the next byte from memory.<br>
The CPU class has a fetch_address method, which fetches the next byte from memory and returns it as an 8-bit address.<br>


## memory.py

### ROM
The ROM class represents read-only memory, which contains the instructions that the CPU will execute. It takes as input a size parameter, which represents the size of the ROM in bytes, and an optional content parameter, which is a list of bytes representing the initial contents of the ROM.<br>

The ROM class has a read method, which reads a byte from memory at the specified address. It also has a write method, which raises a RuntimeError because ROM is read-only.<br><br>

### RAM
The RAM class represents read-write memory, which is used to store data that the CPU needs to perform its operations. It takes as input a size parameter, which represents the size of the RAM in bytes, and an optional bit_width parameter, which specifies the number of bits used to represent each byte in memory.<br>

The RAM class has a read method, which reads a byte from memory at the specified address. It also has a write method, which writes a byte to memory at the specified address.<br>

The RAM class also has read_word and write_word methods, which are used to read and write 16-bit words to memory. These methods are useful for working with data types that are larger than a single byte.<br>

## registers.py

The Registers class represents the set of registers in the CPU. Registers are used to store data that the CPU needs to perform its operations, such as the program counter and the accumulator.<br>

The Registers class has a read method, which takes a register index and returns the value stored in that register. It also has a write method, which takes a register index and a value, and stores that value in the specified register.<br>

The Registers class defines several constants for register indices, including A, B, C, D, E, F, X, Y, SP, and PC. These constants can be used in place of raw register indices to make the code more readable.<br>

The Registers class has a registers attribute, which is a list of register values. It also has a num_registers attribute, which indicates the number of registers in the set. By default, the Registers class initializes with ten registers, but this can be customized by passing a different value to the num_registers parameter when creating an instance of the class.<br>

## assemblyer.py

The Assembler class is responsible for translating human-readable assembly code into machine code that can be executed by the CPU. It has a dictionary opcode_map that maps the assembly instructions to their corresponding opcodes in machine code. For example, the assembly instruction mvi (move immediate value) is mapped to the opcode 0x02.<br>

The class also has a register_map dictionary that maps the names of the CPU's registers to their corresponding addresses in memory. For example, the register A is mapped to the address 0x00.<br>

The assemble method takes in the assembly source code as input and returns the corresponding bytecode that can be executed by the CPU. It uses a two-pass process to translate the assembly code to bytecode.<br>

In the first pass, the method identifies any labels in the code and adds them to a dictionary labels. A label is identified as any line that ends with a colon :. The index of the label is then added to the dictionary.<br>

In the second pass, the method translates each line of assembly code into bytecode. It separates any labels from the instruction and splits the line into parts. It then translates the opcode using the opcode_map dictionary and appends it to the bytecode list. The method then translates any operands using the register_map dictionary or the labels dictionary if they are a label. If the operand is a number, it is simply appended to the bytecode list.<br>

Finally, the method returns the bytecode list, which can be loaded into the computer's memory and executed by the CPU.<br>

## Testing
The test_cpu function sets up a simple test program and runs it on the simulated CPU. The program counts down from 10 and then halts. After the program finishes running, the function prints out the values of the CPU's registers and the contents of memory address 0x10.<br>
