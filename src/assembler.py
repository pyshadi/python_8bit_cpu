class AssemblerError(ValueError):
    pass


class Assembler:
    # mnemonic: (opcode, number of operand bytes)
    instructions = {
        'nop': (0x00, 0), 'mov': (0x01, 2), 'mvi': (0x02, 2), 'ld': (0x03, 2), 'st': (0x04, 2),
        'add': (0x05, 2), 'addi': (0x06, 2), 'adda': (0x07, 2),
        'sub': (0x08, 2), 'subi': (0x09, 2), 'suba': (0x0A, 2),
        'mul': (0x0B, 2), 'muli': (0x0C, 2), 'mula': (0x0D, 2),
        'div': (0x0E, 2), 'divi': (0x0F, 2), 'diva': (0x10, 2),
        'inc': (0x11, 1), 'dec': (0x12, 1),
        'andd': (0x13, 2), 'andi': (0x14, 2), 'anda': (0x15, 2),
        'ord': (0x16, 2), 'ori': (0x17, 2), 'ora': (0x18, 2),
        'xord': (0x19, 2), 'xori': (0x1a, 2), 'xora': (0x1b, 2),
        'rtl': (0x1c, 1), 'rtr': (0x1d, 1), 'shl': (0x1e, 2), 'shr': (0x1f, 2),
        'cmp': (0x20, 2), 'cmpi': (0x21, 2), 'cmpa': (0x22, 2),
        'jmp': (0x23, 1), 'jc': (0x24, 1), 'jnc': (0x25, 1), 'je': (0x26, 3),
        'jz': (0x27, 2), 'jnz': (0x28, 2), 'ja': (0x29, 3), 'jae': (0x30, 3),
        'jb': (0x31, 3), 'jbe': (0x32, 3),
        'push': (0x33, 1), 'pushi': (0x34, 1), 'pusha': (0x35, 1), 'pop': (0x36, 1),
        'call': (0x37, 1), 'ret': (0x38, 0),
        'hlt': (0xff, 0),
    }
    opcode_map = {mnemonic: opcode for mnemonic, (opcode, _) in instructions.items()}

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
    }

    @classmethod
    def _parse_lines(cls, source):
        """
        Yield (line_number, label, parts) for each line. Comments (';') are stripped,
        label is None if the line has none, and parts is empty for label-only lines.
        """
        for line_number, line in enumerate(source.splitlines(), start=1):
            line = line.split(';', 1)[0].strip()
            label = None
            if ':' in line:
                label, line = line.split(':', 1)
                label = label.strip()
                if not label:
                    raise AssemblerError(f"line {line_number}: empty label name")
            parts = [part.strip() for part in line.split(',') if part.strip()]
            if label is None and not parts:
                continue
            yield line_number, label, parts

    @classmethod
    def _lookup_instruction(cls, line_number, mnemonic, operands):
        instruction = cls.instructions.get(mnemonic.lower())
        if instruction is None:
            raise AssemblerError(f"line {line_number}: unknown instruction '{mnemonic}'")
        opcode, operand_count = instruction
        if len(operands) != operand_count:
            raise AssemblerError(
                f"line {line_number}: '{mnemonic}' takes {operand_count} operand(s), got {len(operands)}")
        return opcode

    @classmethod
    def _encode_operand(cls, line_number, part, labels):
        if part.upper() in cls.register_map:
            return cls.register_map[part.upper()]
        if part in labels:
            value = labels[part]
        else:
            try:
                value = int(part, 0)  # accepts decimal, 0x.., 0b.., 0o..
            except ValueError:
                raise AssemblerError(f"line {line_number}: invalid operand '{part}'") from None
        if not 0 <= value <= 0xFF:
            raise AssemblerError(f"line {line_number}: operand '{part}' does not fit in a byte")
        return value

    @classmethod
    def assemble(cls, source):
        """
        Assemble the given source code into bytecode.
        """
        lines = list(cls._parse_lines(source))

        # First pass: record the address of every label.
        labels = {}
        address = 0
        for line_number, label, parts in lines:
            if label is not None:
                if label.upper() in cls.register_map:
                    raise AssemblerError(f"line {line_number}: label '{label}' is a register name")
                if label in labels:
                    raise AssemblerError(f"line {line_number}: duplicate label '{label}'")
                labels[label] = address
            if parts:
                cls._lookup_instruction(line_number, parts[0], parts[1:])
                address += len(parts)

        # Second pass: translate the opcodes and operands.
        bytecode = []
        for line_number, _, parts in lines:
            if not parts:
                continue
            bytecode.append(cls._lookup_instruction(line_number, parts[0], parts[1:]))
            for part in parts[1:]:
                bytecode.append(cls._encode_operand(line_number, part, labels))

        return bytecode
