// hello: prints a greeting one character at a time, then counts to three
char message[] = "HELLO FROM C";

int main() {
    for (int i = 0; message[i]; i++) {
        putchar(message[i]);
    }
    putchar('\n');
    for (int n = 1; n <= 3; n++) {
        print(n);
    }
    return 0;
}
