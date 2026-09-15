// bounce: a ball bounces around the Display; hold fire (space) to leave a trail
int x = 3;
int y = 5;
int dx = 1;
int dy = 1;

int main() {
    clear(BLACK);
    while (1) {
        if (!(keys() & KEY_FIRE)) plot(x, y, BLACK);
        if (x == 0) dx = 1;
        if (x == WIDTH - 1) dx = -1;
        if (y == 0) dy = 1;
        if (y == HEIGHT - 1) dy = -1;
        x += dx;
        y += dy;
        plot(x, y, BRASS);
        frame();
    }
}
