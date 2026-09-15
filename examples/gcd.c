// gcd: greatest common divisors, found with Euclid's algorithm
int gcd(int a, int b) {
    while (b != 0) {
        int remainder = a % b;
        a = b;
        b = remainder;
    }
    return a;
}

int main() {
    print(gcd(48, 18));
    print(gcd(210, 45));
    print(gcd(17, 5));
    return 0;
}
