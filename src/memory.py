class ROM:
    def __init__(self, size, content=None):
        if size is None:
            raise ValueError("Size argument cannot be None")
        self.size = size
        self.memory = [0] * size

        if content is not None:
            for i, value in enumerate(content):
                self.memory[i] = value

    def read(self, address):
        if 0 <= address < self.size:
            return self.memory[address]
        else:
            raise IndexError(f"Address {address} out of bounds for ROM of size {self.size}")

    def write(self, address, value):
        raise RuntimeError("Cannot write to a ROM.")



class RAM:
    def __init__(self, size, bit_width=8):
        self.bit_width = bit_width
        self.size = size
        self.memory = [0] * size

    def read(self, address):
        if 0 <= address < self.size:
            return self.memory[address]
        else:
            raise IndexError(f"Address {address} out of bounds for RAM of size {self.size}")

    def write(self, address, value):
        if 0 <= address < self.size:
            self.memory[address] = value
        else:
            raise IndexError(f"Address {address} out of bounds for RAM of size {self.size}")

    def read_word(self, address):
        """
        Read a 16-bit word from memory, starting at the specified address.
        """
        low_byte = self.read(address)
        high_byte = self.read(address + 1)
        return (high_byte << 8) | low_byte

    def write_word(self, address, value):
        """
        Write a 16-bit word to memory, starting at the specified address.
        """
        low_byte = value & 0xFF
        high_byte = (value >> 8) & 0xFF
        self.write(address, low_byte)
        self.write(address + 1, high_byte)

    def max_address(self):
        return 2 ** self.bit_width - 1
