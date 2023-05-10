class Assembler:
    opcode_map = {
        'nop': 0x00, 'mov': 0x01, 'mvi': 0x02, 'ld': 0x03,
        'st': 0x04, 'add': 0x05, 'addi': 0x06, 'adda': 0x07, 'sub': 0x08,
        'subi': 0x09, 'suba': 0x0A, 'mul': 0x0B, 'muli': 0x0C, 'mula': 0x0D,
        'div': 0x0E, 'divi': 0x0F, 'diva': 0x10, 'inc': 0x11, 'dec': 0x12,
        'andd': 0x13, 'andi': 0x14, 'anda': 0x15, 'ord': 0x16, 'ori': 0x17,
        'ora': 0x18, 'xord': 0x19, 'xori': 0x1a, 'xora': 0x1b, 'rtl': 0x1c,
        'rtr': 0x1d, 'shl': 0x1e, 'shr': 0x1f, 'cmp': 0x20, 'cmpi': 0x21,
        'cmpa': 0x22, 'jmp': 0x23, 'jc': 0x24, 'jnc': 0x25, 'je': 0x26,
        'jz': 0x27, 'jnz': 0x28,  'ja': 0x29, 'jae': 0x30, 'jb': 0x31, 'jbe': 0x32, 'push': 0x33,
        'pushi': 0x34, 'pusha': 0x35, 'pop': 0x36, 'call': 0x37, 'ret': 0x38, 'hlt': 0xff,
    }

    register_map = {
        'A': 0x00,
        'B': 0x01,
        'C': 0x02,
        'D': 0x03,
        'E': 0x04,
        'F': 0x05,
        'G': 0x06,
        'H': 0x07,
        'I': 0x08,
        'J': 0x09,
        'K': 0x0a,
        'L': 0x0b,
        'X': 0x0c,
        'Y': 0x0d,
        'SP': 0x0e,
        'PC': 0x0f,
        # ... and so on for the rest of your registers
    }

    @classmethod
    def assemble(cls, source):
        """
        Assemble the given source code into bytecode.
        """
        bytecode = []
        labels = {}
        lines = source.splitlines()

        # First pass: identify labels
        bytecode_index = 0
        for line in lines:
            line = line.strip()

            # If the line ends with a colon, it's a label.
            if ':' in line:
                label_name, instruction = line.split(':', 1)
                labels[label_name.strip()] = bytecode_index

            else:
                # If not a label or comment, increment bytecode index
                bytecode_index += len([part.strip() for part in line.split(',') if part.strip()])

        # Second pass: translate the opcodes and operands
        bytecode_index = 0
        for line in lines:
            line = line.strip()

            # If the line contains a label, separate it from the instruction
            if ':' in line:
                _, line = line.split(':', 1)

            # Split the line into parts and remove any empty parts.
            parts = [part.strip() for part in line.split(',') if part.strip()]

            # Skip empty lines, comments, and lines without opcodes.
            if not parts or line.startswith(';'):
                continue

            # Translate the opcode.
            opcode = cls.opcode_map.get(parts[0])
            if opcode is None:
                continue  # Skip if the opcode doesn't exist (in case of a label)
            bytecode.append(opcode)
            bytecode_index += 1

            # Translate the remaining parts.
            for part in parts[1:]:
                if part in cls.register_map:
                    bytecode.append(cls.register_map[part])
                elif part in labels:
                    bytecode.append(labels[part])
                else:
                    try:
                        bytecode.append(int(part))
                    except ValueError:
                        raise ValueError(f"Invalid operand: {part}")

                bytecode_index += 1

        return bytecode






