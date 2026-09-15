import base64
import json
from pathlib import Path

import pytest

from src.assembler import Assembler
from src.session import TRACE_LIMIT, Session

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
    assert state["program"]["size"] == 34 and state["program"]["labels"] == 2
    assert [12, 0x18] in state["program"]["lines"]
    assert base64.b64decode(state["program"]["bytecode"]) == bytes(Assembler.assemble(FIBONACCI))
    assert state["program"]["label_list"] == [["loop", 0x09], ["next", 0x15]]
    assert state["current_line"] == 2
    assert state["next"] == {"address": 0, "bytes": [0x02, 0x00, 0x00], "text": "mvi, A, 0"}
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
    assert (second["status"], second["cycles"]) == ("break", 15)


def test_run_to_halt():
    result = loaded().run(max_steps=1000)
    state = result["state"]
    assert result["stopped"] and state["status"] == "halted"
    assert state["cycles"] == 94 and state["registers"][0] == 0x37
    assert state["next"] is None and state["current_line"] is None
    assert len(result["trace"]) == 94
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


def test_full_64_kb_ram():
    state = loaded("mvi, A, 7\nst, A, 0xFFFE\nhlt", ram_size=65536).run()["state"]
    assert ram_of(state)[0xFFFE] == 7
    assert state["memory"]["last_writes"] == []  # hlt wrote nothing
    session = loaded("mvi, A, 7\nst, A, 0xFFFE\nhlt", ram_size=65536)
    session.step()
    assert session.step()["state"]["memory"]["last_writes"] == [0xFFFE]


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


def test_dashboard_manifest_lists_every_module_and_example():
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text())
    assert manifest["python"] == sorted(p.name for p in (ROOT / "src").glob("*.py") if p.name != "__main__.py")
    assert manifest["examples"] == sorted(p.name for p in (ROOT / "examples").glob("*.asm"))
