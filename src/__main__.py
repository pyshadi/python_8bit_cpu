"""
Command-line runner: python3 -m src run PROGRAM [--trace] ...  |  python3 -m src disasm PROGRAM
"""
import argparse
import sys

from src.assembler import Assembler, AssemblerError
from src.cpu import CPU
from src.disassembler import disassemble_all
from src.memory import ROM, RAM
from src.registers import Registers
from src.trace import TRACE_HEADER, StopReason, format_record, format_registers

EXIT_OK, EXIT_ERROR, EXIT_USAGE, EXIT_STEP_LIMIT = 0, 1, 2, 3


def build_parser():
    parser = argparse.ArgumentParser(prog="python3 -m src", description="Assemble and run programs for the 8-bit CPU.")
    commands = parser.add_subparsers(dest="command", required=True)

    run = commands.add_parser("run", help="assemble and run a program")
    run.add_argument("program", help="assembly source file, e.g. examples/fibonacci.asm")
    run.add_argument("--trace", action="store_true", help="print every instruction as it runs")
    run.add_argument("--break", dest="breakpoints", action="append", default=[], metavar="LOCATION",
                     help="stop before the instruction at a label or address (e.g. loop, 0x0018); repeatable")
    run.add_argument("--max-steps", type=int, default=100_000, metavar="N",
                     help="stop after N instructions (default: 100000)")
    run.add_argument("--ram", type=lambda s: int(s, 0), default=1024, metavar="BYTES",
                     help="RAM size in bytes, up to 65536 (default: 1024)")

    disasm = commands.add_parser("disasm", help="assemble a program and print its disassembly")
    disasm.add_argument("program", help="assembly source file")
    return parser


def load_program(path):
    """
    Return (Program, None) or (None, error message).
    """
    try:
        with open(path, encoding="utf-8") as f:
            source = f.read()
    except OSError as e:
        return None, f"cannot read {path}: {e.strerror}"
    try:
        return Assembler.assemble_program(source), None
    except AssemblerError as e:
        return None, f"{path}: {e}"


def resolve_location(location, program):
    if location in program.labels:
        return program.labels[location]
    try:
        return int(location, 0)
    except ValueError:
        return None


def describe_location(address, program, labels):
    line = program.address_lines.get(address)
    where = f"{address:04X}"
    if address in labels:
        where += f" ({labels[address]})"
    return where if line is None else f"{where}, line {line}"


def print_output(cpu, out):
    """
    Print what the program printed with out/outc, if anything.
    """
    text = "".join(cpu.output)
    if text:
        print("Output:", file=out)
        print(text, end="" if text.endswith("\n") else "\n", file=out)


def command_run(args, out, err):
    program, error = load_program(args.program)
    if error:
        print(error, file=err)
        return EXIT_ERROR
    if not 1 <= args.ram <= 0x10000:
        print(f"--ram must be between 1 and 65536 bytes, got {args.ram}", file=err)
        return EXIT_USAGE

    labels = {address: name for name, address in program.labels.items()}
    code = program.bytecode
    cpu = CPU(ROM(max(len(code), 1), code), RAM(args.ram))
    for location in args.breakpoints:
        address = resolve_location(location, program)
        if address is None:
            known = ", ".join(sorted(program.labels)) or "none"
            print(f"--break {location}: no such label (labels: {known}) and not an address", file=err)
            return EXIT_USAGE
        cpu.breakpoints.add(address)

    if args.trace:
        print(TRACE_HEADER, file=out)
    current = [0]  # address of the instruction about to run, for error messages

    def on_step(record):
        current[0] = record.next_address
        if args.trace:
            print(format_record(record, labels), file=out)

    try:
        result = cpu.run_until(max_steps=args.max_steps, on_step=on_step)
    except Exception as e:  # runtime errors from the program itself: stack, divide by zero, bad jumps
        address = current[0]
        if address >= len(code):
            message = f"ran past the end of the program at {address:04X}; is a hlt missing?"
        else:
            message = f"{type(e).__name__} at {describe_location(address, program, labels)}: {e}"
        print(f"{args.program}: {message}", file=err)
        print_output(cpu, out)
        print(format_registers(cpu.registers.registers), file=out)
        return EXIT_ERROR

    print_output(cpu, out)
    pc = cpu.registers.read(Registers.PC)
    if result.reason == StopReason.HALTED:
        print(f"Halted after {cpu.cycles} cycles.", file=out)
        status = EXIT_OK
    elif result.reason == StopReason.BREAKPOINT:
        text = next((i.text(labels) for i in disassemble_all(code) if i.address == pc), "")
        print(f"Stopped at breakpoint {describe_location(pc, program, labels)}: {text} after {cpu.cycles} cycles.",
              file=out)
        status = EXIT_OK
    else:
        print(f"Stopped after {cpu.cycles} cycles (step limit). Use --max-steps to run longer.", file=out)
        status = EXIT_STEP_LIMIT
    print(format_registers(cpu.registers.registers), file=out)
    return status


def command_disasm(args, out, err):
    program, error = load_program(args.program)
    if error:
        print(error, file=err)
        return EXIT_ERROR
    labels = {}
    for name, address in program.labels.items():
        labels.setdefault(address, name)
    for instruction in disassemble_all(program.bytecode):
        for name, address in program.labels.items():
            if address == instruction.address:
                print(f"{'':19}{name}:", file=out)
        raw = " ".join(f"{b:02X}" for b in instruction.bytes)
        print(f"{instruction.address:04X}  {raw:<11}      {instruction.text(labels)}", file=out)
    return EXIT_OK


def main(argv=None, out=None, err=None):
    out = out or sys.stdout
    err = err or sys.stderr
    for stream in (out, err):  # keep "←" from crashing terminals without UTF-8
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    args = build_parser().parse_args(argv)
    if args.command == "run":
        return command_run(args, out, err)
    return command_disasm(args, out, err)


if __name__ == "__main__":
    sys.exit(main())
