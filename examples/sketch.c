// sketch: draw on the Display with the arrow keys; hold fire (space) to wipe it
int x = 16;
int y = 16;

int main() {
    while (1) {
        int held = keys();
        if (held & KEY_FIRE) clear(BLACK);
        if (held & KEY_LEFT) x--;
        if (held & KEY_RIGHT) x++;
        if (held & KEY_UP) y--;
        if (held & KEY_DOWN) y++;
        x &= 31;
        y &= 31;
        plot(x, y, WHITE);
        frame();
    }
}
