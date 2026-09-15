// sieve: the prime numbers below 100, found with the sieve of Eratosthenes
#define LIMIT 100

int composite[LIMIT];

int main() {
    for (int i = 2; i < LIMIT; i++) {
        if (composite[i]) continue;
        print(i);
        for (int j = i + i; j < LIMIT; j += i) {
            composite[j] = 1;
        }
    }
    return 0;
}
