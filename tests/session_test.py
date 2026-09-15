import json
from pathlib import Path

from src.session import TRACE_LIMIT, Session

ROOT = Path(__file__).parent.parent
FIBONACCI = (ROOT / "examples" / "fibonacci.asm").read_text()


def loaded(source=FIBONACCI, breakpoints=()):
    session = Session()
    session.load(source, breakpoints)
    return session


def test_load_reports_program_and_initial_state():
    result = Session().load(FIBONACCI)
    state = result["state"]
    assert result["clear_trace"] and state["status"] == "ready"
    assert state["program"]["size"] == 34 and state["program"]["labels"] == 2
    assert [12, 0x18] in state["program"]["lines"]
    assert state["current_line"] == 2
    assert state["next"] == {"address": 0, "bytes": [0x02, 0x00, 0x00], "text": "mvi, A, 0"}
    assert state["registers"][14] == 1023  # SP at the top of 1 KB RAM


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
                                "effect": "A ← 00"}]
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
    assert loaded().run(max_steps=1000)["state"]["status"] == "halted"


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


def test_dashboard_manifest_lists_every_module_and_example():
    manifest = json.loads((ROOT / "dashboard" / "manifest.json").read_text())
    assert manifest["python"] == sorted(p.name for p in (ROOT / "src").glob("*.py") if p.name != "__main__.py")
    assert manifest["examples"] == sorted(p.name for p in (ROOT / "examples").glob("*.asm"))
