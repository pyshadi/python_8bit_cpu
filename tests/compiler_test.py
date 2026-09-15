from pathlib import Path

import pytest

from src.assembler import Assembler
from src.compiler import CompileError, compile_c
from src.cpu import CPU
from src.memory import KEY_FIRE, KEY_LEFT, RAM, ROM
from src.session import Session
from src.trace import StopReason

EXAMPLES = Path(__file__).parent.parent / "examples"


def machine(source, ram_size=1024):
    program = Assembler.assemble_program(compile_c(source, ram_size).assembly)
    return CPU(ROM(len(program.bytecode), program.bytecode), RAM(ram_size))


def run(source, max_steps=500_000):
    cpu = machine(source)
    result = cpu.run_until(max_steps=max_steps)
    assert result.reason == StopReason.HALTED, "program didn't finish"
    return "".join(cpu.output)


def prints(body, globals_=""):
    return run(f"{globals_}\nint main() {{\n{body}\nreturn 0;\n}}\n")


def numbers(*values):
    return "".join(f"{v}\n" for v in values)


def error(source):
    with pytest.raises(CompileError) as caught:
        compile_c(source)
    return caught.value


# --- Values and operators --------------------------------------------------------------

def test_constants_and_precedence():
    assert prints("print(2 + 3 * 4); print((2 + 3) * 4); print(100 / 7); print(100 % 7); print(1 << 4 | 1);") == \
        numbers(14, 20, 14, 2, 17)


def test_arithmetic_on_variables_wraps_at_a_byte():
    body = """
        int a = 250; int b = 10; int c = 7;
        print(a + b); print(b - c); print(c - b); print(a * 2); print(a / c); print(a % c);
        print(a & 15); print(b | 5); print(a ^ 255); print(~b); print(-c);
        print(b << 3); print(a >> 2); print(b << c); print(a >> c);
    """
    assert prints(body) == numbers(4, 3, 253, 244, 35, 5, 10, 15, 5, 245, 249, 80, 62, 0, 1)


def test_arithmetic_with_computed_operands():
    body = """
        int a = 17; int b = 5;
        print((a + 1) - (b + 1)); print((a + 1) * (b - 1)); print((a + 2) / (b - 1)); print((a + 3) % (b + 1));
        print(3 - a); print(200 / a); print(19 % b);
    """
    assert prints(body) == numbers(12, 72, 4, 2, 242, 11, 4)


def test_comparisons_as_values_and_conditions():
    body = """
        int a = 3; int b = 7; int n = 0;
        print(a < b); print(a > b); print(a <= 3); print(a >= 4); print(a == 3); print(a != b);
        print(b < a + 1); print(a + 4 == b); print(10 > a); print(3 >= a);
        if (a < b) n = n + 1;
        if (b <= a) n = n + 10;
        if (a + 0 >= b - 4) n = n + 100;
        if (a != a) n = n + 1;
        print(n);
    """
    assert prints(body) == numbers(1, 0, 1, 0, 1, 1, 0, 1, 1, 1, 101)


def test_logic_short_circuits():
    source = """
        int calls = 0;
        int touch(int v) { calls++; return v; }
        int main() {
            if (touch(0) && touch(1)) print(99);
            if (touch(1) || touch(1)) print(1);
            print(calls);
            print(!calls); print(!0); print(touch(2) && touch(3)); print(0 || touch(0));
            print(calls);
            return 0;
        }
    """
    assert run(source) == numbers(1, 2, 0, 1, 1, 0, 5)


def test_ternary_and_negative_constants():
    assert prints("int a = 5; print(a > 3 ? 10 : 20); print(a > 9 ? 10 : 20); int m = -1; print(m);") == \
        numbers(10, 20, 255)


def test_compound_assignment_and_increment():
    body = """
        int a = 10; int b = 3;
        a += 5; print(a); a -= b; print(a); a *= 2; print(a); a /= b + 1; print(a); a %= 4; print(a);
        a |= 8; print(a); a &= 12; print(a); a ^= 5; print(a); a <<= 2; print(a); a >>= b; print(a);
        print(a++); print(a); print(++a); print(a--); print(--a);
        int c = a = 7; print(c);
    """
    assert prints(body) == numbers(15, 12, 24, 6, 2, 10, 8, 13, 52, 6, 6, 7, 8, 8, 6, 7)


# --- Statements --------------------------------------------------------------------------

def test_loops_break_and_continue():
    body = """
        int total = 0;
        for (int i = 0; i < 10; i++) { if (i == 3) continue; if (i == 8) break; total += i; }
        print(total);
        int n = 0;
        while (1) { n++; if (n >= 5) break; }
        print(n);
        do { n--; } while (n > 2);
        print(n);
        do n++; while (0);
        print(n);
    """
    assert prints(body) == numbers(25, 5, 2, 3)


def test_blocks_shadow_names():
    assert prints("int a = 1; { int a = 2; print(a); } print(a);") == numbers(2, 1)


def test_functions_with_parameters_and_nested_calls():
    source = """
        int add3(int a, int b, int c) { return a + b + c; }
        int twice(int v) { return v * 2; }
        void show(int v) { print(v); }
        int main() {
            show(add3(twice(1), twice(2), add3(1, 1, 1)));
            print(add3(1, 2, 3) + twice(5));
            return 0;
        }
    """
    assert run(source) == numbers(9, 16)


def test_recursion_keeps_each_call_s_variables():
    source = """
        int factorial(int n) {
            int result = 1;
            if (n > 1) result = n * factorial(n - 1);
            return result;
        }
        int ackermann(int m, int n) {
            if (m == 0) return n + 1;
            if (n == 0) return ackermann(m - 1, 1);
            return ackermann(m - 1, ackermann(m, n - 1));
        }
        int main() { print(factorial(5)); print(ackermann(2, 3)); return 0; }
    """
    assert run(source) == numbers(120, 9)


def test_prototypes_allow_mutual_recursion():
    source = """
        int is_odd(int n);
        int is_even(int n) { if (n == 0) return 1; return is_odd(n - 1); }
        int is_odd(int n) { if (n == 0) return 0; return is_even(n - 1); }
        int main() { print(is_even(10)); print(is_odd(7)); return 0; }
    """
    assert run(source) == numbers(1, 1)


def test_main_returning_halts_and_function_named_like_a_register():
    assert run("int a() { return 4; }\nint main() { print(a()); }") == numbers(4)


# --- Globals, arrays and #define --------------------------------------------------------

def test_globals_arrays_and_defines():
    source = """
        #define SIZE 5
        #define START 'A'
        int counter = 3;
        int squares[SIZE];
        int primes[] = {2, 3, 5, 7};
        char word[] = "HI";
        int main() {
            for (int i = 0; i < SIZE; i++) squares[i] = i * i;
            print(squares[4]); print(squares[counter]);
            primes[counter] += 10; print(primes[3]);
            print(primes[1]++); print(primes[1]); print(--primes[0]);
            int k = 0;
            while (word[k]) { putchar(word[k] + 32); k++; }
            putchar(START); putchar('\\n');
            print(counter);
            return 0;
        }
    """
    assert run(source) == numbers(16, 9, 17, 3, 4, 1) + "hiA\n" + numbers(3)


def test_strings_and_characters():
    assert prints('puts("HELLO, C"); putchar(\'x\'); putchar(10); print(\'\\x41\');') == "HELLO, C\nx\n65\n"


def test_peek_and_poke():
    body = """
        poke(0x0300, 42); print(peek(0x0300));
        int i = 3; poke(0x0300 + i, 9); print(peek(0x0303)); print(peek(i + 0x0300));
        poke(i, 5); print(peek(3));
    """
    assert prints(body) == numbers(42, 9, 9, 5)


# --- Screen, keys, random, frames -------------------------------------------------------

def test_plot_pixel_and_clear():
    cpu = machine("int main() { clear(RED); plot(2, 1, WHITE); plot(33, 0, BRASS); print(pixel(2, 1)); print(pixel(0, 5)); return 0; }")
    cpu.run_until(max_steps=100_000)
    assert "".join(cpu.output) == numbers(3, 1)
    assert cpu.ram.screen[34] == 3 and cpu.ram.screen[1] == 2 and cpu.ram.screen[1023] == 1


def test_keys_rand_and_frame():
    cpu = machine("int main() { while (1) { print(keys() & KEY_LEFT); rand(); frame(); } }")
    cpu.ram.keys = KEY_LEFT | KEY_FIRE
    assert cpu.run_until(max_steps=1000, stop_at_frame=True).reason == StopReason.FRAME
    assert "".join(cpu.output) == numbers(4)


# --- Source map ---------------------------------------------------------------------------

def test_line_map_points_at_the_c_lines():
    compiled = compile_c("int main() {\n    int a = 2;\n\n    print(a);\n    return 0;\n}\n")
    lines = compiled.assembly.splitlines()
    by_c_line = {}
    for asm_line, c_line in compiled.line_map.items():
        by_c_line.setdefault(c_line, []).append(lines[asm_line - 1].strip())
    assert "out, A" in by_c_line[4]
    assert "st, A, 0x0000" in by_c_line[2]
    assert all(not lines[n - 1].startswith((";", " " * 8 + ";")) for n in compiled.line_map)


# --- Errors -------------------------------------------------------------------------------

@pytest.mark.parametrize("source, line, message", [
    ("int main() {\n  int a = 1\n  return a;\n}", 2, "expected ';'"),
    ("int main() {\n  print(b);\n}", 2, "'b' is not declared"),
    ("int helper() { return 1; }", 1, "needs a main function"),
    ("int f(int a) { return a; }\nint main() {\n  f(1, 2);\n}", 3, "f() takes 1 argument, got 2"),
    ("int main() {\n  3 = 4;\n}", 2, "must be a variable"),
    ("int main() {\n  break;\n}", 2, "'break' must be inside a loop"),
    ("int main() {\n  int *p;\n}", 2, "pointers aren't supported"),
    ("#include <stdio.h>\nint main() {}", 1, "#include isn't needed"),
    ('int main() {\n  puts("oops);\n}', 2, "missing its closing"),
    ("int f(int a, int b, int c, int d, int e, int g, int h) {}\nint main() {}", 1, "at most 6 parameters"),
    ("void f() { return 1; }\nint main() {}", 1, "can't return a value"),
    ("int main() {\n  int a = 300;\n}", 2, "300 doesn't fit in a byte"),
    ("int main() {\n  int a[3];\n}", 2, "arrays must be declared outside functions"),
    ("int a[2] = {1, 2, 3};\nint main() {}", 1, "has 2 elements but 3 values"),
    ("int a[4];\nint main() {\n  a[4] = 1;\n}", 3, "index 4 is outside a[4]"),
    ("int a[4];\nint main() {\n  a = 1;\n}", 3, "'a' is an array"),
    ("int n = 2;\nint main() {\n  n();\n}", 3, "'n' is a variable, not a function"),
    ("int print(int v) { return v; }\nint main() {}", 1, "'print' is built in"),
    ("int main() {\n  switch (1) {}\n}", 2, "'switch' isn't supported yet"),
    ("int main() {\n  print(1 / 0);\n}", 2, "division by zero"),
    ("int main() {\n  /* never closed\n}", 2, "missing its closing */"),
    ("int main() {\n  else print(1);\n}", 2, "'else' without a matching 'if'"),
    ("int a[256];\nint b[256];\nint c[256];\nint d[256];\nint main() {}", 4, "choose a larger RAM size"),
    ("int main() {\n  int x = @;\n}", 2, "unexpected character '@'"),
])
def test_errors_name_the_line(source, line, message):
    problem = error(source)
    assert problem.line == line
    assert message in problem.message


def test_larger_ram_allows_more_variables():
    compile_c("int a[256];\nint b[256];\nint c[256];\nint d[256];\nint main() {}", ram_size=4096)


# --- Examples and the session command ---------------------------------------------------

EXPECTED_OUTPUT = {
    "bitcount.c": numbers(5, 8, 0),
    "countdown.c": numbers(10, 9, 8, 7, 6, 5, 4, 3, 2, 1) + "LIFTOFF\n",
    "factorial.c": numbers(1, 2, 6, 24, 120),
    "fib.c": numbers(1, 1, 2, 3, 5, 8, 13, 21, 34, 55),
    "gcd.c": numbers(6, 15, 1),
    "hello.c": "HELLO FROM C\n" + numbers(1, 2, 3),
    "sieve.c": numbers(2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97),
    "stripes.c": "",
}
INTERACTIVE = {"bounce.c", "sketch.c"}


def test_every_c_example_is_checked():
    assert sorted(p.name for p in EXAMPLES.glob("*.c")) == sorted([*EXPECTED_OUTPUT, *INTERACTIVE])


@pytest.mark.parametrize("name", sorted(EXPECTED_OUTPUT))
def test_c_example_output(name):
    assert run((EXAMPLES / name).read_text()) == EXPECTED_OUTPUT[name]


def test_stripes_example_draws_the_stripes():
    cpu = machine((EXAMPLES / "stripes.c").read_text())
    assert cpu.run_until(max_steps=200_000).reason == StopReason.HALTED
    assert [cpu.ram.screen[i] for i in (0, 1, 3, 33, 31 * 32 + 31)] == [0, 1, 3, 2, 2]


def test_sketch_example_draws_with_the_keys_and_wipes_on_fire():
    cpu = machine((EXAMPLES / "sketch.c").read_text())
    cpu.run_until(max_steps=20_000, stop_at_frame=True)
    centre = 16 * 32 + 16
    assert cpu.ram.screen[centre] == 3
    cpu.ram.keys = KEY_LEFT
    cpu.run_until(max_steps=20_000, stop_at_frame=True)
    assert cpu.ram.screen[centre] == 3 and cpu.ram.screen[centre - 1] == 3
    cpu.ram.keys = KEY_FIRE
    cpu.run_until(max_steps=20_000, stop_at_frame=True)
    assert cpu.ram.screen[centre] == 0 and cpu.ram.screen[centre - 1] == 3


def test_bounce_example_moves_the_ball_and_keeps_a_trail_on_fire():
    cpu = machine((EXAMPLES / "bounce.c").read_text())
    for _ in range(2):
        assert cpu.run_until(max_steps=20_000, stop_at_frame=True).reason == StopReason.FRAME
    assert cpu.ram.screen[7 * 32 + 5] == 2 and cpu.ram.screen[6 * 32 + 4] == 0
    cpu.ram.keys = KEY_FIRE
    cpu.run_until(max_steps=20_000, stop_at_frame=True)
    assert cpu.ram.screen[7 * 32 + 5] == 2 and cpu.ram.screen[8 * 32 + 6] == 2


def test_session_compile_command():
    session = Session()
    result = session.compile("int main() { print(7); return 0; }")
    assert result["compile_error"] is None
    compiled = result["compiled"]
    assert "out, A" in compiled["assembly"] and all(len(pair) == 2 for pair in compiled["lines"])
    session.load(compiled["assembly"])
    assert session.run()["state"]["output"]["text"] == "7\n"

    failed = session.compile("int main() {\n  print(x);\n}")
    assert failed["compiled"] is None
    assert failed["compile_error"] == {"line": 2, "message": "'x' is not declared"}
