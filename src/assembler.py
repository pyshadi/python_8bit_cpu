class AssemblerError(ValueError):
    pass


class Assembler:
    # Operand kinds: r = register (1 byte), i = immediate (1 byte),
    # a = address (2 bytes, little-endian: low byte first).
    OPERAND_SIZES = {'r': 1, 'i': 1, 'a': 2}

    # mnemonic: (opcode, operand kinds)
    instructions = {
        'nop': (0x00, ''), 'mov': (0x01, 'rr'), 'mvi': (0x02, 'ri'), 'ld': (0x03, 'ra'), 'st': (0x04, 'ra'),
        'add': (0x05, 'rr'), 'addi': (0x06, 'ri'), 'adda': (0x07, 'ra'),
        'sub': (0x08, 'rr'), 'subi': (0x09, 'ri'), 'suba': (0x0A, 'ra'),
        'mul': (0x0B, 'rr'), 'muli': (0x0C, 'ri'), 'mula': (0x0D, 'ra'),
        'div': (0x0E, 'rr'), 'divi': (0x0F, 'ri'), 'diva': (0x10, 'ra'),
        'inc': (0x11, 'r'), 'dec': (0x12, 'r'),
        'andd': (0x13, 'rr'), 'andi': (0x14, 'ri'), 'anda': (0x15, 'ra'),
        'ord': (0x16, 'rr'), 'ori': (0x17, 'ri'), 'ora': (0x18, 'ra'),
        'xord': (0x19, 'rr'), 'xori': (0x1a, 'ri'), 'xora': (0x1b, 'ra'),
        'rtl': (0x1c, 'r'), 'rtr': (0x1d, 'r'), 'shl': (0x1e, 'ri'), 'shr': (0x1f, 'ri'),
        'cmp': (0x20, 'rr'), 'cmpi': (0x21, 'ri'), 'cmpa': (0x22, 'ra'),
        'jmp': (0x23, 'a'), 'jc': (0x24, 'a'), 'jnc': (0x25, 'a'), 'je': (0x26, 'ria'),
        'jz': (0x27, 'ra'), 'jnz': (0x28, 'ra'), 'ja': (0x29, 'ria'), 'jae': (0x2a, 'ria'),
        'jb': (0x2b, 'ria'), 'jbe': (0x2c, 'ria'),
        'push': (0x2d, 'r'), 'pushi': (0x2e, 'i'), 'pusha': (0x2f, 'a'), 'pop': (0x30, 'r'),
        'call': (0x31, 'a'), 'ret': (0x32, ''),
        'inv': (0x33, 'r'), 'sar': (0x34, 'r'),
        'hlt': (0xff, ''),
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
        """
        Return (opcode, operand kinds) for an instruction, checking the operand count.
        """
        instruction = cls.instructions.get(mnemonic.lower())
        if instruction is None:
            raise AssemblerError(f"line {line_number}: unknown instruction '{mnemonic}'")
        opcode, kinds = instruction
        if len(operands) != len(kinds):
            raise AssemblerError(
                f"line {line_number}: '{mnemonic}' takes {len(kinds)} operand(s), got {len(operands)}")
        return opcode, kinds

    @classmethod
    def _encode_operand(cls, line_number, kind, part, labels):
        """
        Encode one operand of the given kind as a list of bytes.
        """
        is_register = part.upper() in cls.register_map
        if kind == 'r':
            if not is_register:
                raise AssemblerError(f"line {line_number}: expected a register, got '{part}'")
            return [cls.register_map[part.upper()]]
        if is_register:
            raise AssemblerError(f"line {line_number}: expected a number or label, got register '{part}'")

        if part in labels:
            value = labels[part]
        else:
            try:
                value = int(part, 0)  # accepts decimal, 0x.., 0b.., 0o..
            except ValueError:
                raise AssemblerError(f"line {line_number}: invalid operand '{part}'") from None

        if kind == 'i':
            if not 0 <= value <= 0xFF:
                raise AssemblerError(f"line {line_number}: operand '{part}' does not fit in a byte")
            return [value]
        if not 0 <= value <= 0xFFFF:
            raise AssemblerError(f"line {line_number}: address '{part}' does not fit in 16 bits")
        return [value & 0xFF, value >> 8]

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
                _, kinds = cls._lookup_instruction(line_number, parts[0], parts[1:])
                address += 1 + sum(cls.OPERAND_SIZES[kind] for kind in kinds)

        # Second pass: translate the opcodes and operands.
        bytecode = []
        for line_number, _, parts in lines:
            if not parts:
                continue
            opcode, kinds = cls._lookup_instruction(line_number, parts[0], parts[1:])
            bytecode.append(opcode)
            for kind, part in zip(kinds, parts[1:]):
                bytecode.extend(cls._encode_operand(line_number, kind, part, labels))

        return bytecode
