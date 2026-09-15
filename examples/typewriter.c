// typewriter: press letters, digits, space and Enter on the Display's keyboard; each press appears in Output
int main() {
    int last = 0;
    while (1) {
        int c = keychar();
        if (c != last && c != 0) putchar(c);
        last = c;
        frame();
    }
}
