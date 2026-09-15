import base64
from pathlib import Path

import pytest

from src.assembler import Assembler
from src.cpu import CPU
from src.memory import KEY_RIGHT, KEYS, RANDOM, RAM, ROM, SCREEN_BASE, random_byte
from src.registers import Registers
from src.session import Session
from src.trace import StopReason

EXAMPLES = Path(__file__).parent.parent / "examples"


def machine(source, ram_size=1024):
    code = Assembler.assemble(source)
    return CPU(ROM(len(code), code), RAM(ram_size))


def reg(cpu, name):
    return cpu.registers.read(getattr(Registers, name))


def test_64_kb_ram_stops_below_the_devices():
    cpu = machine("hlt", 65536)
    assert cpu.ram.size == 0xF000
    assert reg(cpu, "SP") == 0xEFFF


def test_screen_is_mapped_whatever_the_ram_size():
    cpu = machine("mvi, A, 3\nst, A, 0xF021\nld, B, 0xF021\nhlt")
    cpu.run_until()
    assert cpu.ram.screen[33] == 3 and reg(cpu, "B") == 3


def test_address_space_errors():
    ram = RAM(1024)
    with pytest.raises(IndexError, match="out of bounds"):
        ram.read(0x0400)
    with pytest.raises(IndexError, match="out of bounds"):
        ram.read(0xF400)
    with pytest.raises(IndexError, match=r"FF00 \(keys\) is read-only"):
        ram.write(KEYS, 1)
    with pytest.raises(IndexError, match=r"FF01 \(random\) is read-only"):
        ram.write(RANDOM, 1)


def test_indexed_addressing_through_x_y():
    cpu = machine("mvi, X, 0x01\nmvi, Y, 0xFF\nmvi, A, 42\nstx, A\ninxy\nstx, A\n"
                  "ld, B, 0x01FF\nld, C, 0x0200\nldx, D\nhlt")
    cpu.run_until()
    assert (reg(cpu, "B"), reg(cpu, "C"), reg(cpu, "D")) == (42, 42, 42)
    assert (reg(cpu, "X"), reg(cpu, "Y")) == (0x02, 0x00)


def test_inxy_wraps_at_ffff():
    cpu = machine("mvi, X, 0xFF\nmvi, Y, 0xFF\ninxy\nhlt")
    cpu.run_until()
    assert (reg(cpu, "X"), reg(cpu, "Y")) == (0, 0)


def test_keys_are_readable():
    cpu = machine("ld, A, 0xFF00\nhlt")
    cpu.ram.keys = KEY_RIGHT
    cpu.run_until()
    assert reg(cpu, "A") == KEY_RIGHT


def test_random_depends_only_on_the_cycle_and_replays_after_undo():
    cpu = machine("ld, A, 0xFF01\nld, B, 0xFF01\nhlt")
    cpu.step()
    record = cpu.step()
    assert reg(cpu, "A") == random_byte(0) and reg(cpu, "B") == random_byte(1)
    cpu.undo(record)
    cpu.step()
    assert reg(cpu, "B") == random_byte(1)
    assert len({random_byte(cycle) for cycle in range(256)}) > 100


def test_frame_stops_run_until_when_asked():
    cpu = machine("loop: inc, A\nframe\njmp, loop")
    first = cpu.run_until(max_steps=100, stop_at_frame=True)
    assert (first.reason, first.steps, reg(cpu, "A")) == (StopReason.FRAME, 2, 1)
    second = cpu.run_until(max_steps=100, stop_at_frame=True)
    assert (second.reason, second.steps, reg(cpu, "A")) == (StopReason.FRAME, 3, 2)
    assert cpu.run_until(max_steps=50).reason == StopReason.STEP_LIMIT


def test_screen_writes_are_undone_snapshotted_and_reset():
    cpu = machine("mvi, A, 2\nst, A, 0xF000\nhlt")
    power_on = cpu.snapshot()
    cpu.step()
    record = cpu.step()
    assert record.ram_writes == {SCREEN_BASE: (0, 2)} and cpu.ram.screen[0] == 2
    after = cpu.snapshot()
    cpu.undo(record)
    assert cpu.ram.screen[0] == 0
    cpu.restore(after)
    assert cpu.ram.screen[0] == 2
    cpu.reset()
    assert cpu.snapshot() == power_on


def test_session_screen_keys_and_frames():
    session = Session()
    session.load("loop: ld, A, 0xFF00\nst, A, 0xF000\nframe\njmp, loop")
    session.set_keys(KEY_RIGHT)
    result = session.run(max_steps=1000, stop_at_frame=True)
    assert result["frame"] and not result["stopped"]
    state = result["state"]
    assert base64.b64decode(state["screen"])[0] == KEY_RIGHT and state["keys"] == KEY_RIGHT
    assert session.run(max_steps=1000, quiet=True, stop_at_frame=True) == {"stopped": False, "status": "paused", "frame": True}

    session.load("hlt")
    assert session.cpu.ram.keys == KEY_RIGHT  # held keys survive loading another program
    with pytest.raises(ValueError, match="keys must be a byte"):
        session.set_keys(300)


def test_session_can_edit_and_undo_screen_pixels():
    session = Session()
    session.load("hlt")
    session.poke_ram(SCREEN_BASE + 5, 3)
    assert base64.b64decode(session.state()["screen"])[5] == 3
    session.back()
    assert base64.b64decode(session.state()["screen"])[5] == 0


def test_keys_example_moves_the_dot():
    code = Assembler.assemble((EXAMPLES / "keys.asm").read_text())
    cpu = CPU(ROM(len(code), code), RAM(1024))
    assert cpu.run_until(max_steps=10_000, stop_at_frame=True).reason == StopReason.FRAME
    centre = 16 * 32 + 16
    assert cpu.ram.screen[centre] == 2
    cpu.ram.keys = KEY_RIGHT
    cpu.run_until(max_steps=10_000, stop_at_frame=True)
    assert cpu.ram.screen[centre] == 0 and cpu.ram.screen[centre + 1] == 2
