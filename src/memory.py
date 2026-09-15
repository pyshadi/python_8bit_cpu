"""
ROM holds the program; RAM holds data, the stack and the memory-mapped devices.

16-bit address space:
    0000-EFFF  RAM (as much as the chosen size allows)
    F000-F3FF  screen: 32 x 32 pixels, one byte per pixel, colors 0-3, row by row
    FF00       keys, read-only: bit 0 up, 1 down, 2 left, 3 right, 4 Enter
    FF01       random byte, read-only
    FF02       character key, read-only: the ASCII code of the letter, digit, space or Enter (10) held, or 0
"""

DEVICE_BASE = 0xF000
SCREEN_BASE = 0xF000
SCREEN_WIDTH = 32
SCREEN_HEIGHT = 32
SCREEN_END = SCREEN_BASE + SCREEN_WIDTH * SCREEN_HEIGHT
KEYS = 0xFF00
RANDOM = 0xFF01
CHAR_KEY = 0xFF02
KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER = 0x01, 0x02, 0x04, 0x08, 0x10
READ_ONLY_DEVICES = {KEYS: "keys", RANDOM: "random", CHAR_KEY: "character key"}


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


def random_byte(cycle, address=RANDOM):
    """
    A pseudo-random byte that depends only on the cycle count, so Back and rewind replay it exactly.
    """
    x = (cycle * 2654435761 + address * 40503) & 0xFFFFFFFF
    x ^= x >> 15
    x = (x * 2246822519) & 0xFFFFFFFF
    x ^= x >> 13
    return x & 0xFF


class RAM:
    def __init__(self, size, bit_width=8):
        self.bit_width = bit_width
        # The top of the address space belongs to the devices, so RAM stops below DEVICE_BASE.
        self.size = min(size, DEVICE_BASE)
        self.memory = [0] * self.size
        self.screen = [0] * (SCREEN_WIDTH * SCREEN_HEIGHT)
        self.keys = 0                   # keys currently held, set by the dashboard
        self.char_key = 0               # character key currently held, set by the dashboard
        self.cycle_source = lambda: 0   # the CPU connects its cycle counter, used by RANDOM
        # When set to a dict, write() records each address's value before its first write.
        self.write_log = None

    def read(self, address):
        if 0 <= address < self.size:
            return self.memory[address]
        if SCREEN_BASE <= address < SCREEN_END:
            return self.screen[address - SCREEN_BASE]
        if address == KEYS:
            return self.keys
        if address == RANDOM:
            return random_byte(self.cycle_source(), address)
        if address == CHAR_KEY:
            return self.char_key
        raise IndexError(self._out_of_bounds(address))

    def write(self, address, value):
        if address in READ_ONLY_DEVICES:
            raise IndexError(f"Address {address:04X} ({READ_ONLY_DEVICES[address]}) is read-only")
        old = self.peek(address)
        if self.write_log is not None and address not in self.write_log:
            self.write_log[address] = old
        self.poke(address, value)

    def peek(self, address):
        """
        Read a RAM or screen byte (not the input devices).
        """
        if 0 <= address < self.size:
            return self.memory[address]
        if SCREEN_BASE <= address < SCREEN_END:
            return self.screen[address - SCREEN_BASE]
        raise IndexError(self._out_of_bounds(address))

    def poke(self, address, value):
        """
        Set a RAM or screen byte without logging it (used when undoing).
        """
        if 0 <= address < self.size:
            self.memory[address] = value
        elif SCREEN_BASE <= address < SCREEN_END:
            self.screen[address - SCREEN_BASE] = value
        else:
            raise IndexError(self._out_of_bounds(address))

    def _out_of_bounds(self, address):
        return f"Address {address} out of bounds for RAM of size {self.size}"

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
