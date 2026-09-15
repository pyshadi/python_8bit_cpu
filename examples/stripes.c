// stripes: fills the Display with diagonal color stripes
int main() {
    for (int y = 0; y < HEIGHT; y++) {
        for (int x = 0; x < WIDTH; x++) {
            plot(x, y, (x + y) & 3);
        }
    }
    return 0;
}
