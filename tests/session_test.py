import base64
import json
from pathlib import Path

import pytest

from src.assembler import Assembler
from src.session import HISTORY_LIMIT, TRACE_LIMIT, Session

ROOT = Path(__file__).parent.parent
FIBONACCI = (ROOT / "examples" / "fibonacci.asm").read_text()


def loaded(source=FIBONACCI, breakpoints=(), ram_size=None):
    session = Session()
    session.load(source, breakpoints, ram_size)
    return session


def ram_of(state):
    return base64.b64decode(state["memory"]["ram"])


def test_load_reports_program_and_initial_state():
    result = Session().load(FIBONACCI)
    state = result["state"]
    assert result["clear_trace"] and state["status"] == "ready"
    assert state["program"]["size"] == 36 and state["program"]["labels"] == 2
    assert [12, 0x18] in state["program"]["lines"]
    assert base64.b64decode(state["program"]["bytecode"]) == bytes(Assembler.assemble(FIBONACCI))
    assert state["program"]["label_list"] == [["loop", 0x09], ["next", 0x15]]
    assert state["current_line"] == 2
    assert state["next"] == {"address": 0, "bytes": [0x02, 0x00, 0x00], "text": "mvi, A, 0",
                             "mnemonic": "mvi", "operands": [["r", 0], ["i", 0]]}
    assert state["history"] == {"size": 0, "rewind_from": None}
    assert state["registers"][14] == 1023  # SP at the top of 1 KB RAM
    assert state["memory"]["size"] == 1024 and ram_of(state) == bytes(1024)


def test_assembler_error_has_line_and_keeps_breakpoints():
    state = Session().load("nop\nmvx, A, 1", breakpoints=[1])["state"]
    assert state["status"] == "error"
    assert state["error"] == {"line": 2, "message": "unknown instruction 'mvx'"}
    assert state["program"] is None
    assert state["breakpoints"] == [1]


def test_breakpoints_only_on_instruction_lines():
    session = loaded(breakpoints=[1, 10, 12])
    assert session.state()["breakpoints"] == [12]
    assert session.set_breakpoints([5, 11])["state"]["breakpoints"] == [5, 11]


def test_step_returns_trace_entry_and_written_registers():
    result = loaded().step()
    assert result["trace"] == [{"cycle": 1, "address": 0, "bytes": [0x02, 0x00, 0x00], "text": "mvi, A, 0",
                                "effect": "A ← 00", "all": True, "ram": False, "jump": False}]
    state = result["state"]
    assert (state["status"], state["cycles"], state["written"], state["current_line"]) == ("paused", 1, ["A"], 3)
    assert not result["stopped"]


def test_run_stops_at_breakpoint_and_continues():
    session = loaded(breakpoints=[12])
    first = session.run(max_steps=1000)
    assert first["stopped"]
    state = first["state"]
    assert (state["status"], state["cycles"], state["current_line"]) == ("break", 6, 12)
    assert state["next"]["text"] == "add, A, B"

    second = session.run(max_steps=1000)["state"]
    assert (second["status"], second["cycles"]) == ("break", 16)


def test_run_to_halt():
    result = loaded().run(max_steps=1000)
    state = result["state"]
    assert result["stopped"] and state["status"] == "halted"
    assert state["cycles"] == 104 and state["registers"][0] == 0x37
    assert state["next"] is None and state["current_line"] is None
    assert len(result["trace"]) == 104
    assert state["output"]["text"] == "1\n1\n2\n3\n5\n8\n13\n21\n34\n55\n"
    assert result["trace"][-1]["effect"] == "halted"
    assert list(ram_of(state)[0x3F5:0x3FF]) == [55, 34, 21, 13, 8, 5, 3, 2, 1, 1]


def test_run_in_chunks_reports_step_limit_as_not_stopped():
    session = loaded()
    result = session.run(max_steps=10)
    assert not result["stopped"] and result["state"]["status"] == "paused"
    assert result["state"]["cycles"] == 10


def test_trace_is_limited_to_most_recent_entries():
    session = loaded("loop: jmp, loop")
    trace = session.run(max_steps=TRACE_LIMIT + 50)["trace"]
    assert len(trace) == TRACE_LIMIT
    assert trace[-1]["cycle"] == TRACE_LIMIT + 50


def test_trace_keeps_recent_memory_writes_and_jumps_separately():
    session = loaded("loop: pushi, 1\npop, A\nmvi, B, 2\nmvi, B, 3\njmp, loop")
    trace = session.run(max_steps=2000)["trace"]
    assert sum(e["all"] for e in trace) == TRACE_LIMIT
    assert sum(e["ram"] for e in trace) == TRACE_LIMIT
    assert sum(e["jump"] for e in trace) == TRACE_LIMIT
    assert len({e["cycle"] for e in trace}) == len(trace)
    assert [e["cycle"] for e in trace] == sorted(e["cycle"] for e in trace)
    oldest_in_all = min(e["cycle"] for e in trace if e["all"])
    assert any(e["ram"] and e["cycle"] < oldest_in_all for e in trace)


def test_quiet_runs_keep_the_trace_for_the_next_result():
    session = loaded()
    assert session.run(max_steps=5, quiet=True) == {"stopped": False, "status": "paused"}
    result = session.run(max_steps=5)
    assert [e["cycle"] for e in result["trace"]] == list(range(1, 11))
    assert json.loads(session.handle('{"command": "state"}'))["trace"] == []


def test_ram_size_choice():
    state = Session().load(FIBONACCI, ram_size=4096)["state"]
    assert state["memory"]["size"] == 4096 and len(ram_of(state)) == 4096
    assert state["registers"][14] == 4095
    with pytest.raises(ValueError, match="RAM size must be one of 1024, 4096, 65536 bytes, got 2000"):
        Session().load(FIBONACCI, ram_size=2000)
    reply = json.loads(Session().handle('{"command": "load", "source": "hlt", "ram_size": 2000}'))
    assert reply["error"].startswith("RAM size must be one of")


def test_64_kb_ram_ends_below_the_devices():
    state = loaded("mvi, A, 7\nst, A, 0xEFFE\nhlt", ram_size=65536).run()["state"]
    assert state["memory"]["size"] == 0xF000 and state["registers"][14] == 0xEFFF
    assert ram_of(state)[0xEFFE] == 7
    assert state["memory"]["last_writes"] == []  # hlt wrote nothing
    session = loaded("mvi, A, 7\nst, A, 0xEFFE\nhlt", ram_size=65536)
    session.step()
    assert session.step()["state"]["memory"]["last_writes"] == [0xEFFE]


def test_last_ram_writes_follow_each_step():
    session = loaded()
    for _ in range(3):
        session.step()
    assert session.step()["state"]["memory"]["last_writes"] == [0x3FE]         # push, B
    assert session.step()["state"]["memory"]["last_writes"] == [0x3FC, 0x3FD]  # call, next
    assert session.step()["state"]["memory"]["last_writes"] == []              # mov, E, B


def test_return_addresses_on_the_stack_are_marked():
    session = loaded(breakpoints=[12])
    state = session.run(max_steps=1000)["state"]  # inside the first call
    assert state["registers"][14] == 0x3FC
    assert state["memory"]["return_cells"] == [0x3FC, 0x3FD]
    ram = ram_of(state)
    assert ram[0x3FC] | (ram[0x3FD] << 8) == 0x000E and ram[0x3FE] == 1

    state = session.run(max_steps=1000)["state"]  # second call; 03FD now holds a pushed value
    assert state["memory"]["return_cells"] == [0x3FB, 0x3FC]


def test_reset_and_load_forget_memory_marks():
    session = loaded(breakpoints=[12])
    session.run(max_steps=1000)
    memory = session.reset()["state"]["memory"]
    assert memory["return_cells"] == [] and memory["last_writes"] == [] and ram_of(session.state()) == bytes(1024)


def test_runtime_error_points_to_line():
    state = loaded("nop\nstart: pop, A\nhlt").run()["state"]
    assert state["status"] == "error"
    assert state["error"]["line"] == 2
    assert state["error"]["message"].startswith("StackUnderflowError at 0001: stack underflow")


def test_missing_hlt():
    state = loaded("mvi, A, 1").run()["state"]
    assert state["error"] == {"line": None, "message": "Ran past the end of the program at 0003. Is a hlt missing?"}


def test_halted_and_error_sessions_ignore_step_and_run_until_reset():
    session = loaded("hlt")
    session.run()
    assert session.step()["state"]["cycles"] == 1
    assert session.run(quiet=True) == {"stopped": True, "status": "halted"}
    reset = session.reset()
    assert reset["clear_trace"] and reset["state"]["status"] == "ready" and reset["state"]["cycles"] == 0


def test_handle_speaks_json():
    session = Session()
    result = json.loads(session.handle(json.dumps({"command": "load", "source": FIBONACCI, "breakpoints": [12]})))
    assert result["state"]["breakpoints"] == [12]
    assert json.loads(session.handle('{"command": "run", "max_steps": 1000}'))["state"]["status"] == "break"
    assert json.loads(session.handle('{"command": "nope"}')) == {"error": "unknown command 'nope'"}


def test_empty_session_state():
    state = Session().state()
    assert state["status"] == "empty" and state["program"] is None and state["registers"][14] == 1023
    assert state["memory"]["size"] == 1024


def test_back_undoes_steps_and_edits_in_order():
    session = loaded()
    power_on = session.state()
    for _ in range(4):
        session.step()
    after_four = session.state()
    session.poke_register("B", 0x42)
    session.poke_ram(0x100, 7)

    result = session.back()  # the RAM edit
    assert result["rewound"]
    assert ram_of(result["state"])[0x100] == 0 and result["state"]["registers"][1] == 0x42
    assert session.back()["state"] == after_four  # the register edit

    for _ in range(4):
        state = session.back()["state"]
    assert state == power_on
    assert session.back()["state"] == power_on  # nothing left to undo


def test_back_after_halt_and_after_a_runtime_error():
    session = loaded("hlt")
    assert session.run()["state"]["status"] == "halted"
    assert session.back()["state"]["status"] == "ready"

    session = loaded("nop\npop, A")
    assert session.run()["state"]["status"] == "error"
    state = session.back()["state"]  # undoes the nop; the failed pop never took effect
    assert (state["status"], state["error"], state["cycles"], state["registers"][15]) == ("ready", None, 0, 0)


def test_rewind_matches_a_fresh_run_to_the_same_cycle():
    session = loaded()
    session.run(max_steps=70, quiet=True)
    result = session.rewind(65)  # back to just before the seventh "call, next"
    state = result["state"]
    assert result["rewound"] and state["cycles"] == 64 and state["next"]["text"] == "call, next"
    assert max(entry["cycle"] for entry in result["trace"]) == 64
    assert state["output"]["text"] == "1\n1\n2\n3\n5\n8\n"  # the seventh term hasn't been printed yet

    fresh = loaded()
    fresh.run(max_steps=64)
    assert state == fresh.state()


def test_rewind_reaches_back_1000_changes():
    session = loaded("loop: jmp, loop")
    session.run(max_steps=1500)
    assert session.state()["history"] == {"size": HISTORY_LIMIT, "rewind_from": 501}
    with pytest.raises(ValueError, match="cycle 500 is further back than the last 1000 changes"):
        session.rewind(500)
    assert session.rewind(501)["state"]["cycles"] == 500
    with pytest.raises(ValueError, match="cycle 501 hasn't run yet"):
        session.rewind(501)


def test_edits_are_checked_and_let_a_failed_program_continue():
    session = loaded("pop, A\nhlt")
    assert session.run()["state"]["status"] == "error"
    state = session.poke_register("SP", 0x3FE)["state"]  # give pop something to read
    assert state["status"] == "paused" and state["error"] is None
    assert session.run()["state"]["status"] == "halted"

    with pytest.raises(ValueError, match=r"A must be between 0 and 255 \(0xFF\), got 256"):
        session.poke_register("A", 256)
    with pytest.raises(ValueError, match="unknown register 'Q'"):
        session.poke_register("Q", 1)
    with pytest.raises(ValueError, match="address 0x0400 is outside 1024 bytes of RAM"):
        session.poke_ram(0x400, 1)
    with pytest.raises(ValueError, match="load a program"):
        Session().poke_ram(0, 1)
    reply = json.loads(session.handle('{"command": "poke_ram", "address": 0, "value": 300}'))
    assert reply == {"error": "RAM bytes must be between 0 and 255 (0xFF), got 300"}


def test_preview_shows_the_next_instruction_without_running_it():
    session = loaded(breakpoints=[12])
    state = session.run(max_steps=1000)["state"]  # next: add, A, B with A=0 and B=1
    assert state["next"]["mnemonic"] == "add"
    assert state["next"]["operands"] == [["r", 0], ["r", 1]]
    assert state["preview"] == {"registers": {"A": 1, "F": 0}, "ram": [], "next_address": 0x1B,
                                "jumped": False, "halted": False,
                                "alu": [{"op": "add", "args": [0, 1], "result": 1}], "output": ""}
    assert session.state() == state

    call_preview = loaded().run(max_steps=4)["state"]["preview"]  # next: call, next
    assert call_preview["jumped"] and call_preview["next_address"] == 0x15
    assert call_preview["ram"] == [[0x3FC, 0x0E], [0x3FD, 0x00]]

    assert loaded("pop, A").state()["preview"]["error"].startswith("StackUnderflowError")


@pytest.mark.parametrize("source, steps, expected_alu", [
    ("mvi, B, 5\ninc, B\nhlt", 1, [{"op": "add", "args": [5, 1], "result": 6}]),   # inc uses the ALU's add
    ("mvi, A, 5\ncmpi, A, 7\nhlt", 1, [{"op": "compare", "args": [5, 7], "result": None}]),
    ("mvi, B, 0b0110\nshl, B, 1\nhlt", 1, [{"op": "shift_left", "args": [6, 1], "result": 12}]),
    ("mvi, B, 7\nmov, C, B\nhlt", 1, []),                                          # moves bypass the ALU
    ("mvi, C, 1\njnz, C, end\nend: hlt", 1, []),                                   # the decoder compares
    ("pushi, 3\npop, A\nhlt", 1, []),
    ("call, sub\nhlt\nsub: ret", 0, []),
])
def test_preview_records_exactly_which_alu_operations_run(source, steps, expected_alu):
    session = loaded(source)
    for _ in range(steps):
        session.step()
    preview = session.state()["preview"]
    assert preview["alu"] == expected_alu
    # recording is temporary: the CPU keeps its real ALU
    assert type(session.cpu.alu).__name__ == "ALU"


def test_program_output_in_state_preview_and_trace_and_undone_by_back():
    session = loaded("mvi, A, 42\nout, A\nmvi, B, 72\noutc, B\nhlt")
    session.step()
    assert session.state()["preview"]["output"] == "42\n"
    session.step()
    result = session.step()
    assert result["state"]["output"] == {"text": "42\n", "truncated": False}
    session.run()
    assert session.state()["output"]["text"] == "42\nH"
    trace_effects = [entry["effect"] for entry in session.reset()["trace"]]
    assert trace_effects == [] and session.state()["output"]["text"] == ""

    session.run()
    session.back()  # undo hlt
    session.back()  # undo outc
    assert session.state()["output"]["text"] == "42\n"
    session.rewind(2)  # before out, A
    assert session.state()["output"]["text"] == ""


def test_output_trace_effect():
    trace = loaded("mvi, A, 7\nout, A\nhlt").run()["trace"]
    assert trace[1]["effect"] == "output '7\\n'"


def test_long_output_is_truncated_to_the_most_recent_text():
    session = loaded("mvi, A, 65\nloop: outc, A\njmp, loop")
    session.run(max_steps=2 * 25_000)
    output = session.state()["output"]
    assert output["truncated"] and len(output["text"]) == 20_000 and set(output["text"]) == {"A"}


def test_dashboard_manifest_lists_every_module_and_example():
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text())
    assert manifest["python"] == sorted(p.name for p in (ROOT / "src").glob("*.py") if p.name != "__main__.py")
    assert manifest["examples"] == sorted(p.name for pattern in ("*.asm", "*.c") for p in (ROOT / "examples").glob(pattern))
