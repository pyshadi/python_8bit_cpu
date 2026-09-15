import io
from pathlib import Path

from src.__main__ import main

FIBONACCI = str(Path(__file__).parent.parent / "examples" / "fibonacci.asm")


def run_cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    status = main(list(argv), out=out, err=err)
    return status, out.getvalue(), err.getvalue()


def line_for_cycle(output, cycle):
    return next(line for line in output.splitlines() if line.split()[:1] == [str(cycle)])


def test_run_to_halt():
    status, out, err = run_cli("run", FIBONACCI)
    assert status == 0 and err == ""
    assert "Halted after 94 cycles." in out
    assert "A 37  B 59  C 00" in out
    assert "PC 0015  SP 03F5  F 01 Z" in out


def test_trace_lines():
    status, out, _ = run_cli("run", FIBONACCI, "--trace")
    assert status == 0
    lines = out.splitlines()
    assert lines[0].split() == ["cycle", "addr", "bytes", "instruction", "effect"]
    assert line_for_cycle(out, 56) == "    56  000E  12 02        dec, C            C ← 04 · F ← 00"
    assert line_for_cycle(out, 57) == "    57  0010  28 02 09 00  jnz, C, loop      taken → 0009 (loop)"
    assert line_for_cycle(out, 59) == ("    59  000B  31 15 00     call, next        SP ← 03F6 · [03F6] ← 0E · "
                                       "[03F7] ← 00 · PC ← 0015 (next)")
    assert line_for_cycle(out, 94).endswith("hlt               halted")


def test_break_at_label_and_address():
    status, out, _ = run_cli("run", FIBONACCI, "--break", "next")
    assert status == 0
    assert "Stopped at breakpoint 0015 (next), line 11: mov, E, B after 5 cycles." in out

    status, out, _ = run_cli("run", FIBONACCI, "--break", "0x18")
    assert "Stopped at breakpoint 0018, line 12: add, A, B after 6 cycles." in out


def test_unknown_breakpoint_label():
    status, _, err = run_cli("run", FIBONACCI, "--break", "nowhere")
    assert status == 2
    assert "--break nowhere: no such label (labels: loop, next)" in err


def test_step_limit():
    status, out, _ = run_cli("run", FIBONACCI, "--max-steps", "10")
    assert status == 3
    assert "Stopped after 10 cycles (step limit)." in out


def test_assembler_error(tmp_path):
    bad = tmp_path / "bad.asm"
    bad.write_text("nop\nmvx, A, 1\n")
    status, _, err = run_cli("run", str(bad))
    assert status == 1
    assert err.strip() == f"{bad}: line 2: unknown instruction 'mvx'"


def test_runtime_error_names_location(tmp_path):
    program = tmp_path / "underflow.asm"
    program.write_text("nop\nstart: pop, A\nhlt\n")
    status, _, err = run_cli("run", str(program))
    assert status == 1
    assert "StackUnderflowError at 0001 (start), line 2: stack underflow" in err


def test_missing_hlt(tmp_path):
    program = tmp_path / "nohlt.asm"
    program.write_text("mvi, A, 1\n")
    status, _, err = run_cli("run", str(program))
    assert status == 1
    assert "ran past the end of the program at 0003; is a hlt missing?" in err


def test_missing_file():
    status, _, err = run_cli("run", "does/not/exist.asm")
    assert status == 1
    assert err.startswith("cannot read does/not/exist.asm")


def test_disasm():
    status, out, _ = run_cli("disasm", FIBONACCI)
    assert status == 0
    lines = out.splitlines()
    assert lines[0] == "0000  02 00 00         mvi, A, 0"
    assert "loop:" in lines[3] and lines[4] == "0009  2D 01            push, B"
    assert "0010  28 02 09 00      jnz, C, loop" in lines
