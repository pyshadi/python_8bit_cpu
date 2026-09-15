// factorial: the factorials of 1 to 5, each worked out with a loop
int factorial(int n) {
    int result = 1;
    for (int i = 2; i <= n; i++) {
        result *= i;
    }
    return result;
}

int main() {
    for (int n = 1; n <= 5; n++) {
        print(factorial(n));
    }
    return 0;
}
