// bitcount: counts the 1 bits in a few bytes
int bits(int value) {
    int count = 0;
    while (value) {
        count += value & 1;
        value >>= 1;
    }
    return count;
}

int main() {
    print(bits(0b10110110));
    print(bits(255));
    print(bits(0));
    return 0;
}
