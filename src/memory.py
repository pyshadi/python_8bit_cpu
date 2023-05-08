class ROM:
    def __init__(self, size, content=None):
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
    def __init__(self, size):
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
