// fib: the first ten Fibonacci numbers, found by a recursive function
int fib(int n) {
    if (n < 2) return n;
    return fib(n - 1) + fib(n - 2);
}

int main() {
    for (int i = 1; i <= 10; i++) {
        print(fib(i));
    }
    return 0;
}
