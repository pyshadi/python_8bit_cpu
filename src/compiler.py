"""
A small C compiler for the 8-bit CPU. It turns C source into assembly for src/assembler.py.

The language is C with 8-bit values:
- int, char and byte are all unsigned bytes (0 to 255); arithmetic wraps around
- global variables and arrays (with initial values), local variables, function parameters
- if/else, while, do/while, for, break, continue, return, recursion
- the usual operators, including compound assignment, ++/--, && || ! and ?:
- #define NAME value
- built-in functions for output, the screen, the keys and memory (see BUILTINS)

Code generation: expressions leave their value in register A, with B as a scratch register and the
stack for intermediate values. Every variable lives at a fixed RAM address. A function saves its own
variables on the stack when it starts and restores them when it returns, so recursion works.
Arguments arrive in registers C, D, E, G, H and I.
"""
import re
from collections import namedtuple
from dataclasses import dataclass

PARAM_REGISTERS = ("C", "D", "E", "G", "H", "I")
REGISTER_NAMES = {"A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L", "X", "Y", "SP", "PC"}
TYPE_WORDS = {"int", "char", "byte", "unsigned", "void", "const"}
CONTROL_WORDS = {"if", "else", "while", "for", "do", "return", "break", "continue"}
UNSUPPORTED_WORDS = {"signed", "long", "short", "float", "double", "struct", "union", "enum", "typedef",
                     "static", "extern", "sizeof", "switch", "case", "default", "goto"}
KEYWORDS = TYPE_WORDS | CONTROL_WORDS | UNSUPPORTED_WORDS

# name: number of arguments
BUILTINS = {
    "print": 1,    # print a number and a new line
    "putchar": 1,  # print one character
    "puts": 1,     # print a string in quotes and a new line
    "plot": 3,     # plot(x, y, color): set a pixel; x and y wrap at 32
    "pixel": 2,    # pixel(x, y): the color of a pixel
    "clear": 1,    # clear(color): fill the screen
    "keys": 0,     # the keys held: KEY_UP, KEY_DOWN, KEY_LEFT, KEY_RIGHT, KEY_ENTER
    "keychar": 0,  # the character key held ('A', '7', ' ', or 10 for Enter), or 0
    "rand": 0,     # a random byte
    "frame": 0,    # end of a frame: wait for the next 1/30 second at full speed
    "peek": 1,     # peek(address): read a byte of memory
    "poke": 2,     # poke(address, value): write a byte of memory
    "halt": 0,     # stop the machine
}

PREDEFINED = {
    "KEY_UP": 1, "KEY_DOWN": 2, "KEY_LEFT": 4, "KEY_RIGHT": 8, "KEY_ENTER": 16,
    "BLACK": 0, "RED": 1, "BRASS": 2, "WHITE": 3,
    "WIDTH": 32, "HEIGHT": 32,
}

SCREEN_HIGH_BYTE = 0xF0
SCREEN_END_HIGH_BYTE = 0xF4
KEYS_ADDRESS = 0xFF00
RANDOM_ADDRESS = 0xFF01
CHAR_KEY_ADDRESS = 0xFF02
STACK_ROOM = 128          # bytes of RAM kept free for the stack
DEVICE_BASE = 0xF000

BINARY_PRECEDENCE = {
    "||": 1, "&&": 2, "|": 3, "^": 4, "&": 5, "==": 6, "!=": 6, "<": 7, ">": 7, "<=": 7, ">=": 7,
    "<<": 8, ">>": 8, "+": 9, "-": 9, "*": 10, "/": 10, "%": 10,
}
ASSIGN_OPS = {"=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "<<=", ">>="}
COMPARISONS = {"==", "!=", "<", ">", "<=", ">="}
COMMUTATIVE = {"+", "*", "&", "|", "^"}
IMMEDIATE_FORMS = {"+": "addi", "-": "subi", "*": "muli", "/": "divi", "&": "andi", "|": "ori", "^": "xori",
                   "<<": "shl", ">>": "shr"}
REGISTER_FORMS = {"+": "add", "-": "sub", "*": "mul", "/": "div", "&": "andd", "|": "ord", "^": "xord"}
MEMORY_FORMS = {"+": "adda", "-": "suba", "*": "mula", "/": "diva", "&": "anda", "|": "ora", "^": "xora"}
CONSTANT_JUMPS = {"<": "jb", "<=": "jbe", ">": "ja", ">=": "jae"}
NEGATED = {"<": ">=", ">=": "<", "<=": ">", ">": "<="}
MIRRORED = {"<": ">", ">": "<", "<=": ">=", ">=": "<=", "==": "==", "!=": "!="}


class CompileError(ValueError):
    def __init__(self, line, message):
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


@dataclass
class CompiledProgram:
    assembly: str
    line_map: dict    # assembly line -> C line, for every instruction


def compile_c(source, ram_size=1024):
    """
    Compile C source to assembly. Raises CompileError with the C line of the problem.
    """
    tokens = tokenize(source)
    items = Parser(tokens).program()
    return CodeGenerator(items, ram_size).generate()


# --- Tokens ---------------------------------------------------------------------------

Token = namedtuple("Token", "kind value line")   # kind: num, str, name, op, eof

_TOKEN = re.compile(r"""
    (?P<space>[ \t\r\f\v]+)
  | (?P<newline>\n)
  | (?P<line_comment>//[^\n]*)
  | (?P<block_comment>/\*.*?\*/)
  | (?P<open_comment>/\*)
  | (?P<directive>\#[^\n]*)
  | (?P<number>[0-9][A-Za-z0-9_]*)
  | (?P<char>'(?:\\.|[^\\'\n])*')
  | (?P<string>"(?:\\.|[^\\"\n])*")
  | (?P<name>[A-Za-z_][A-Za-z0-9_]*)
  | (?P<op><<=|>>=|\+\+|--|&&|\|\||<<|>>|<=|>=|==|!=|[-+*/%&|^]=|[-+*/%&|^~!<>=?:;,(){}\[\]])
""", re.VERBOSE | re.DOTALL)

_ESCAPES = {"n": 10, "t": 9, "r": 13, "0": 0, "\\": 92, "'": 39, '"': 34}


def tokenize(source, macros=None, first_line=1, directives=True):
    if macros is None:
        macros = {name: [Token("num", value, 0)] for name, value in PREDEFINED.items()}
    tokens = []
    line = first_line
    pos = 0
    line_start = True
    while pos < len(source):
        match = _TOKEN.match(source, pos)
        if not match:
            char = source[pos]
            if char == '"':
                raise CompileError(line, "this string is missing its closing \"")
            if char == "'":
                raise CompileError(line, "this character is missing its closing '")
            raise CompileError(line, f"unexpected character '{char}'")
        kind, text, pos = match.lastgroup, match.group(), match.end()
        if kind == "newline":
            line += 1
            line_start = True
            continue
        if kind in ("space", "line_comment"):
            continue
        if kind == "block_comment":
            line += text.count("\n")
            continue
        if kind == "open_comment":
            raise CompileError(line, "this comment is missing its closing */")
        if kind == "directive":
            if not (directives and line_start):
                raise CompileError(line, "'#' must start a line")
            _directive(text, line, macros)
            continue
        line_start = False
        if kind == "number":
            token = Token("num", _number(text, line), line)
        elif kind == "char":
            codes = _decode(text[1:-1], line)
            if len(codes) != 1:
                raise CompileError(line, "a character in single quotes must be exactly one character")
            token = Token("num", codes[0], line)
        elif kind == "string":
            token = Token("str", _decode(text[1:-1], line), line)
        elif kind == "name":
            token = Token("name", text, line)
        else:
            token = Token("op", text, line)
        _expand(token, macros, tokens, frozenset())
    if directives:
        tokens.append(Token("eof", None, line))
    return tokens


def _directive(text, line, macros):
    match = re.match(r"#\s*define\s+([A-Za-z_]\w*)(.*)$", text)
    if not match:
        word = re.match(r"#\s*(\w*)", text).group(1)
        if word == "include":
            raise CompileError(line, "#include isn't needed: print, plot, keys and the other built-ins are always there")
        raise CompileError(line, f"#{word} isn't supported; only #define NAME value")
    name, body = match.groups()
    if body.startswith("("):
        raise CompileError(line, "#define with parameters isn't supported")
    macros[name] = tokenize(body, macros, line, directives=False)


def _expand(token, macros, out, active):
    if token.kind == "name" and token.value in macros and token.value not in active:
        for replacement in macros[token.value]:
            _expand(replacement._replace(line=token.line), macros, out, active | {token.value})
    else:
        out.append(token)


def _number(text, line):
    try:
        if text.isdigit():
            return int(text, 10)
        if text[:2].lower() in ("0x", "0b"):
            return int(text, 0)
    except ValueError:
        pass
    raise CompileError(line, f"'{text}' isn't a number")


def _decode(body, line):
    codes = []
    i = 0
    while i < len(body):
        char = body[i]
        if char == "\\":
            i += 1
            escape = body[i]
            if escape == "x":
                digits = re.match(r"[0-9a-fA-F]{1,2}", body[i + 1:])
                if not digits:
                    raise CompileError(line, "\\x needs hex digits, like \\x41")
                codes.append(int(digits.group(), 16))
                i += len(digits.group())
            elif escape in _ESCAPES:
                codes.append(_ESCAPES[escape])
            else:
                raise CompileError(line, f"unknown escape \\{escape}")
        else:
            if ord(char) > 255:
                raise CompileError(line, f"'{char}' isn't a character the machine can print")
            codes.append(ord(char))
        i += 1
    return codes


# --- Parser ---------------------------------------------------------------------------

class Node:
    def __init__(self, kind, line, **fields):
        self.kind = kind
        self.line = line
        self.__dict__.update(fields)


def _describe(token):
    if token.kind == "eof":
        return "the end of the program"
    if token.kind == "str":
        return "a string"
    return f"'{token.value}'"


def _unsupported(word, line):
    if word == "signed":
        return CompileError(line, "values are unsigned bytes (0 to 255), so 'signed' isn't supported")
    if word in ("long", "short", "float", "double", "struct", "union", "enum"):
        return CompileError(line, f"'{word}' isn't supported: every value is an 8-bit int, char or byte")
    if word in ("switch", "case", "default"):
        return CompileError(line, f"'{word}' isn't supported yet; use if and else")
    return CompileError(line, f"'{word}' isn't supported")


class Parser:
    def __init__(self, tokens):
        self.tokens = tokens
        self.pos = 0

    @property
    def tok(self):
        return self.tokens[self.pos]

    def peek(self, offset=1):
        return self.tokens[min(self.pos + offset, len(self.tokens) - 1)]

    def at(self, value):
        return self.tok.kind in ("op", "name") and self.tok.value == value

    def next(self):
        token = self.tok
        if token.kind != "eof":
            self.pos += 1
        return token

    def expect(self, value):
        if not self.at(value):
            # A missing ';' belongs to the line before the next token
            line = self.tokens[self.pos - 1].line if value == ";" and self.pos else self.tok.line
            raise CompileError(line, f"expected '{value}' but found {_describe(self.tok)}")
        return self.next()

    def expect_name(self, what):
        token = self.tok
        if token.kind == "name" and token.value in UNSUPPORTED_WORDS:
            raise _unsupported(token.value, token.line)
        if token.kind != "name" or token.value in KEYWORDS:
            raise CompileError(token.line, f"expected {what} but found {_describe(token)}")
        return self.next()

    # Declarations

    def program(self):
        items = []
        while self.tok.kind != "eof":
            items.append(self.top_level())
        return Node("program", self.tok.line, items=items)

    def type_spec(self):
        """'int' or 'void' for a type made of type words, or None when there is no type here."""
        words = []
        while self.tok.kind == "name" and (self.tok.value in TYPE_WORDS or self.tok.value in UNSUPPORTED_WORDS):
            if self.tok.value in UNSUPPORTED_WORDS:
                raise _unsupported(self.tok.value, self.tok.line)
            words.append(self.next().value)
        if not words:
            return None
        if "void" in words:
            if len(words) > 1:
                raise CompileError(self.tok.line, "void can't be combined with other type words")
            return "void"
        if words == ["const"]:
            raise CompileError(self.tok.line, "expected a type such as int after const")
        if self.at("*"):
            raise CompileError(self.tok.line, "pointers aren't supported yet; use an array")
        return "int"

    def top_level(self):
        start = self.tok
        type_ = self.type_spec()
        if type_ is None:
            if start.kind == "name" and start.value not in KEYWORDS and self.peek().kind == "op" and self.peek().value == "(":
                raise CompileError(start.line, f"'{start.value}' needs a return type, like int {start.value}(...)")
            raise CompileError(start.line, f"expected a declaration such as int main() but found {_describe(start)}")
        name = self.expect_name("a name")
        if self.at("("):
            return self.function(type_, name)
        if type_ == "void":
            raise CompileError(name.line, "a variable can't be void")
        return Node("globals", start.line, decls=self.declarators(name))

    def declarators(self, name):
        decls = []
        while True:
            is_array, size, init = False, None, None
            if self.at("["):
                self.next()
                is_array = True
                if not self.at("]"):
                    size = self.expression()
                self.expect("]")
            if self.at("="):
                self.next()
                init = self.initializer_list() if self.at("{") else self.assignment()
            decls.append(Node("decl", name.line, name=name.value, is_array=is_array, size=size, init=init))
            if not self.at(","):
                break
            self.next()
            if self.at("*"):
                raise CompileError(self.tok.line, "pointers aren't supported yet; use an array")
            name = self.expect_name("a variable name")
        self.expect(";")
        return decls

    def initializer_list(self):
        line = self.expect("{").line
        items = []
        while not self.at("}"):
            items.append(self.assignment())
            if not self.at(","):
                break
            self.next()
        self.expect("}")
        return Node("init_list", line, items=items)

    def function(self, type_, name):
        self.expect("(")
        params = []
        if self.at("void") and self.peek().kind == "op" and self.peek().value == ")":
            self.next()
        elif not self.at(")"):
            while True:
                param_type = self.type_spec()
                if param_type is None:
                    raise CompileError(self.tok.line, f"expected a parameter type such as int but found {_describe(self.tok)}")
                if param_type == "void":
                    raise CompileError(self.tok.line, "a parameter can't be void")
                params.append(self.expect_name("a parameter name"))
                if self.at("["):
                    raise CompileError(self.tok.line, "array parameters aren't supported; use a global array")
                if not self.at(","):
                    break
                self.next()
        self.expect(")")
        if self.at(";"):
            self.next()
            return Node("prototype", name.line, name=name.value, params=params, returns_void=type_ == "void")
        if not self.at("{"):
            raise CompileError(self.tok.line, f"expected '{{' to start the body of {name.value}() but found {_describe(self.tok)}")
        body = self.block()
        return Node("function", name.line, name=name.value, params=params, returns_void=type_ == "void", body=body)

    # Statements

    def block(self):
        line = self.expect("{").line
        statements = []
        while not self.at("}"):
            if self.tok.kind == "eof":
                raise CompileError(line, "this '{' is never closed")
            statements.append(self.statement())
        end_line = self.next().line
        return Node("block", line, statements=statements, end_line=end_line)

    def local_declaration(self):
        line = self.tok.line
        type_ = self.type_spec()
        if type_ == "void":
            raise CompileError(line, "a variable can't be void")
        name = self.expect_name("a variable name")
        if self.at("("):
            raise CompileError(line, "functions must be defined outside other functions")
        return Node("locals", line, decls=self.declarators(name))

    def statement(self):
        token = self.tok
        line = token.line
        if self.at("{"):
            return self.block()
        if token.kind == "name" and (token.value in TYPE_WORDS or token.value in UNSUPPORTED_WORDS):
            return self.local_declaration()
        if self.at("if"):
            self.next()
            self.expect("(")
            condition = self.expression()
            self.expect(")")
            then = self.statement()
            otherwise = None
            if self.at("else"):
                self.next()
                otherwise = self.statement()
            return Node("if", line, condition=condition, then=then, otherwise=otherwise)
        if self.at("while"):
            self.next()
            self.expect("(")
            condition = self.expression()
            self.expect(")")
            return Node("while", line, condition=condition, body=self.statement())
        if self.at("do"):
            self.next()
            body = self.statement()
            self.expect("while")
            self.expect("(")
            condition = self.expression()
            self.expect(")")
            self.expect(";")
            return Node("do", line, body=body, condition=condition)
        if self.at("for"):
            self.next()
            self.expect("(")
            init = None
            if self.at(";"):
                self.next()
            elif self.tok.kind == "name" and self.tok.value in TYPE_WORDS:
                init = self.local_declaration()
            else:
                init = Node("expr", self.tok.line, expr=self.expression())
                self.expect(";")
            condition = None if self.at(";") else self.expression()
            self.expect(";")
            step = None if self.at(")") else self.expression()
            self.expect(")")
            return Node("for", line, init=init, condition=condition, step=step, body=self.statement())
        if self.at("return"):
            self.next()
            value = None if self.at(";") else self.expression()
            self.expect(";")
            return Node("return", line, value=value)
        if self.at("break") or self.at("continue"):
            self.next()
            self.expect(";")
            return Node(token.value, line)
        if self.at(";"):
            self.next()
            return Node("empty", line)
        if self.at("else"):
            raise CompileError(line, "'else' without a matching 'if'")
        expr = self.expression()
        self.expect(";")
        return Node("expr", line, expr=expr)

    # Expressions

    def expression(self):
        return self.assignment()

    def assignment(self):
        left = self.ternary()
        if self.tok.kind == "op" and self.tok.value in ASSIGN_OPS:
            op = self.next()
            if left.kind not in ("var", "index"):
                raise CompileError(op.line, f"the left side of '{op.value}' must be a variable or an array element")
            return Node("assign", op.line, op=op.value, target=left, value=self.assignment())
        return left

    def ternary(self):
        condition = self.binary(1)
        if self.at("?"):
            line = self.next().line
            yes = self.expression()
            self.expect(":")
            return Node("ternary", line, condition=condition, yes=yes, no=self.ternary())
        return condition

    def binary(self, min_precedence):
        left = self.unary()
        while self.tok.kind == "op" and BINARY_PRECEDENCE.get(self.tok.value, 0) >= min_precedence:
            op = self.next()
            right = self.binary(BINARY_PRECEDENCE[op.value] + 1)
            left = Node("binary", op.line, op=op.value, left=left, right=right)
        return left

    def unary(self):
        token = self.tok
        if token.kind == "op" and token.value in ("-", "+", "!", "~"):
            self.next()
            return Node("unary", token.line, op=token.value, operand=self.unary())
        if token.kind == "op" and token.value in ("++", "--"):
            self.next()
            target = self.unary()
            if target.kind not in ("var", "index"):
                raise CompileError(token.line, f"'{token.value}' needs a variable or an array element")
            return Node("incdec", token.line, op=token.value, prefix=True, target=target)
        if token.kind == "op" and token.value in ("*", "&"):
            raise CompileError(token.line, "pointers aren't supported yet; use an array")
        return self.postfix()

    def postfix(self):
        node = self.primary()
        while True:
            if self.at("["):
                if node.kind != "var":
                    raise CompileError(self.tok.line, "only arrays can be indexed")
                self.next()
                index = self.expression()
                self.expect("]")
                node = Node("index", node.line, name=node.name, index=index)
            elif self.at("("):
                if node.kind != "var":
                    raise CompileError(self.tok.line, "only functions can be called")
                self.next()
                args = []
                if not self.at(")"):
                    while True:
                        args.append(self.expression())
                        if not self.at(","):
                            break
                        self.next()
                self.expect(")")
                node = Node("call", node.line, name=node.name, args=args)
            elif self.tok.kind == "op" and self.tok.value in ("++", "--"):
                if node.kind not in ("var", "index"):
                    raise CompileError(self.tok.line, f"'{self.tok.value}' needs a variable or an array element")
                op = self.next()
                node = Node("incdec", op.line, op=op.value, prefix=False, target=node)
            else:
                return node

    def primary(self):
        token = self.tok
        if token.kind == "num":
            self.next()
            return Node("num", token.line, value=token.value)
        if token.kind == "str":
            self.next()
            return Node("str", token.line, codes=token.value)
        if token.kind == "name":
            if token.value in UNSUPPORTED_WORDS:
                raise _unsupported(token.value, token.line)
            if token.value in KEYWORDS:
                raise CompileError(token.line, f"expected a value but found '{token.value}'")
            self.next()
            return Node("var", token.line, name=token.value)
        if self.at("("):
            self.next()
            node = self.expression()
            self.expect(")")
            return node
        raise CompileError(token.line, f"expected a value but found {_describe(token)}")


# --- Code generation --------------------------------------------------------------------

class Symbol:
    def __init__(self, name, address, size, is_array):
        self.name = name
        self.address = address
        self.size = size
        self.is_array = is_array


class Function:
    def __init__(self, node):
        self.name = node.name
        self.params = [p.value for p in node.params]
        self.returns_void = node.returns_void
        self.line = node.line
        self.defined = False
        self.label = f"fn.{node.name}" if node.name.upper() in REGISTER_NAMES else node.name


def _address(value):
    return f"0x{value:04X}"


class CodeGenerator:
    def __init__(self, program, ram_size):
        self.program = program
        self.data_limit = min(ram_size, DEVICE_BASE) - STACK_ROOM
        self.globals = {}
        self.functions = {}
        self.variables = []       # (address, size, description) for the header
        self.next_address = 0
        self.init_lines = []      # global initial values, run before main
        self.function_lines = []
        self.out = self.init_lines
        self.line = 1
        self.function = None
        self.scopes = []
        self.loops = []           # (continue label, break label)
        self.label_count = 0

    def error(self, message, line=None):
        return CompileError(self.line if line is None else line, message)

    # Output

    def emit(self, mnemonic, *operands):
        text = ", ".join([mnemonic, *(str(operand) for operand in operands)])
        self.out.append(("        " + text, self.line))

    def label(self, name):
        self.out.append((f"{name}:", None))

    def new_label(self, kind):
        self.label_count += 1
        return f"{self.function.label}.{kind}{self.label_count}"

    def generate(self):
        items = self.program.items
        for item in items:
            if item.kind in ("function", "prototype"):
                self.declare_function(item)
        main = self.functions.get("main")
        if main is None or not main.defined:
            raise CompileError(self.program.line, "a program needs a main function, like: int main() { ... }")
        if main.params:
            raise CompileError(main.line, "main can't take parameters")
        for item in items:
            if item.kind == "globals":
                self.global_declarations(item)
            elif item.kind == "function":
                self.function_definition(item)

        lines = [("; generated from C", None)]
        if self.variables:
            lines.append(("; variables", None))
            for address, size, description in self.variables:
                where = f"{address:04X}" if size == 1 else f"{address:04X}-{address + size - 1:04X}"
                lines.append((f";   {where}  {description}", None))
        lines.append(("", None))
        lines.extend(self.init_lines)
        lines.append(("        call, main" if main.label == "main" else f"        call, {main.label}", main.line))
        lines.append(("        hlt", main.line))
        lines.extend(self.function_lines)
        assembly = "\n".join(text for text, _ in lines) + "\n"
        line_map = {number: c_line for number, (text, c_line) in enumerate(lines, start=1)
                    if c_line is not None and text.startswith("        ")}
        return CompiledProgram(assembly, line_map)

    # Declarations

    def declare_function(self, node):
        name = node.name
        if name in BUILTINS:
            raise CompileError(node.line, f"'{name}' is built in; choose another name")
        if len(node.params) > len(PARAM_REGISTERS):
            raise CompileError(node.line, f"a function can take at most {len(PARAM_REGISTERS)} parameters")
        function = self.functions.get(name)
        if function is None:
            function = self.functions[name] = Function(node)
        elif len(function.params) != len(node.params):
            raise CompileError(node.line, f"'{name}' is declared with {len(function.params)} parameters and here with {len(node.params)}")
        elif function.returns_void != node.returns_void:
            raise CompileError(node.line, f"'{name}' is declared with a different return type")
        if node.kind == "function":
            if function.defined:
                raise CompileError(node.line, f"'{name}' is defined twice")
            function.defined = True
            function.params = [p.value for p in node.params]
            function.line = node.line

    def allocate(self, size, description):
        address = self.next_address
        self.next_address += size
        if self.next_address > self.data_limit:
            raise self.error(f"the variables need more than {self.data_limit} bytes; choose a larger RAM size")
        self.variables.append((address, size, description))
        return address

    def check_new_name(self, name):
        if name in BUILTINS:
            raise self.error(f"'{name}' is built in; choose another name")
        if name in self.functions:
            raise self.error(f"'{name}' is already a function")

    def global_declarations(self, node):
        self.out = self.init_lines
        self.function = None
        for decl in node.decls:
            self.line = decl.line
            self.check_new_name(decl.name)
            if decl.name in self.globals:
                raise self.error(f"'{decl.name}' is declared twice")
            if decl.is_array:
                size, values = self.array_layout(decl)
            else:
                if decl.init is not None and decl.init.kind in ("init_list", "str"):
                    raise self.error(f"'{decl.name}' isn't an array; give it one value")
                size, values = 1, ([self.constant_byte(decl.init)] if decl.init is not None else [])
            description = f"{decl.name}[{size}]" if decl.is_array else decl.name
            symbol = Symbol(decl.name, self.allocate(size, description), size, decl.is_array)
            self.globals[decl.name] = symbol
            loaded = None
            for offset, value in enumerate(values):
                if value == 0:          # RAM starts out as zeros
                    continue
                if value != loaded:
                    self.emit("mvi", "A", value)
                    loaded = value
                self.emit("st", "A", _address(symbol.address + offset))

    def array_layout(self, decl):
        init = decl.init
        if init is None:
            values = []
        elif init.kind == "str":
            values = init.codes + [0]
        elif init.kind == "init_list":
            values = [self.constant_byte(item) for item in init.items]
        else:
            raise self.error(f"give the array '{decl.name}' its values in braces, like {{1, 2, 3}}")
        if decl.size is not None:
            size = self.fold(decl.size)
            if size is None:
                raise self.error(f"the size of '{decl.name}' must be a constant")
            if size < 1:
                raise self.error(f"'{decl.name}' needs at least one element")
            if size > 256:
                raise self.error(f"'{decl.name}' can have at most 256 elements, because indexes are bytes")
            if len(values) > size:
                raise self.error(f"'{decl.name}' has {size} elements but {len(values)} values")
        elif values:
            size = len(values)
        else:
            raise self.error(f"'{decl.name}' needs a size, like {decl.name}[10]")
        return size, values

    def constant_byte(self, node):
        value = self.fold(node)
        if value is None:
            raise self.error("the value of a global variable must be a constant", node.line)
        return self.byte(value, node.line)

    def byte(self, value, line=None):
        if not -128 <= value <= 255:
            raise self.error(f"{value} doesn't fit in a byte (0 to 255)", line)
        return value & 0xFF

    def function_definition(self, node):
        function = self.functions[node.name]
        self.function = function
        self.out = []
        self.line = node.line
        self.scopes = [{}]
        self.loops = []
        first_slot = len(self.variables)
        params = []
        for token in node.params:
            self.line = token.line
            if token.value in self.scopes[0]:
                raise self.error(f"two parameters are named '{token.value}'")
            self.check_new_name(token.value)
            symbol = Symbol(token.value, self.allocate(1, f"{node.name}: {token.value}"), 1, False)
            self.scopes[0][token.value] = symbol
            params.append(symbol)
        for statement in node.body.statements:
            self.statement(statement)
        body = self.out
        ends_with_return = bool(node.body.statements) and node.body.statements[-1].kind == "return"
        slots = [address for address, _, _ in self.variables[first_slot:]]
        save = node.name != "main"

        self.out = []
        self.line = node.line
        self.out.append(("", None))
        self.label(function.label)
        if save:
            for address in slots:
                self.emit("pusha", _address(address))
        for register, symbol in zip(PARAM_REGISTERS, params):
            self.emit("st", register, _address(symbol.address))
        self.out.extend(body)
        self.line = node.body.end_line
        if not ends_with_return and not function.returns_void:
            self.emit("mvi", "A", 0)
        self.label(f"{function.label}.return")
        if save:
            for address in reversed(slots):
                self.emit("pop", "B")
                self.emit("st", "B", _address(address))
        self.emit("ret")
        self.function_lines.extend(self.out)

    # Statements

    def statement(self, node):
        self.line = node.line
        kind = node.kind
        if kind == "block":
            self.scopes.append({})
            for statement in node.statements:
                self.statement(statement)
            self.scopes.pop()
        elif kind == "locals":
            for decl in node.decls:
                self.line = decl.line
                if decl.is_array:
                    raise self.error("arrays must be declared outside functions, as globals")
                if decl.name in self.scopes[-1]:
                    raise self.error(f"'{decl.name}' is already declared here")
                self.check_new_name(decl.name)
                if decl.init is not None and decl.init.kind in ("init_list", "str"):
                    raise self.error(f"'{decl.name}' isn't an array; give it one value")
                symbol = Symbol(decl.name, self.allocate(1, f"{self.function.name}: {decl.name}"), 1, False)
                self.scopes[-1][decl.name] = symbol
                if decl.init is not None:
                    self.value(decl.init)
                    self.emit("st", "A", _address(symbol.address))
        elif kind == "expr":
            self.effect(node.expr)
        elif kind == "if":
            otherwise = self.new_label("else") if node.otherwise else None
            end = self.new_label("endif")
            self.jump(node.condition, otherwise or end, False)
            self.statement(node.then)
            if node.otherwise:
                self.line = node.line
                self.emit("jmp", end)
                self.label(otherwise)
                self.statement(node.otherwise)
            self.label(end)
        elif kind == "while":
            top, end = self.new_label("while"), self.new_label("endwhile")
            self.label(top)
            self.jump(node.condition, end, False)
            self.loop_body(node.body, top, end)
            self.line = node.line
            self.emit("jmp", top)
            self.label(end)
        elif kind == "do":
            top, test, end = self.new_label("do"), self.new_label("test"), self.new_label("enddo")
            self.label(top)
            self.loop_body(node.body, test, end)
            self.label(test)
            self.line = node.condition.line
            self.jump(node.condition, top, True)
            self.label(end)
        elif kind == "for":
            self.scopes.append({})
            if node.init is not None:
                self.statement(node.init)
            top, step, end = self.new_label("for"), self.new_label("step"), self.new_label("endfor")
            self.label(top)
            if node.condition is not None:
                self.line = node.line
                self.jump(node.condition, end, False)
            self.loop_body(node.body, step, end)
            self.label(step)
            self.line = node.line
            if node.step is not None:
                self.effect(node.step)
            self.emit("jmp", top)
            self.label(end)
            self.scopes.pop()
        elif kind == "return":
            if node.value is not None:
                if self.function.returns_void:
                    raise self.error(f"{self.function.name}() is void, so it can't return a value")
                self.value(node.value)
            self.emit("jmp", f"{self.function.label}.return")
        elif kind in ("break", "continue"):
            if not self.loops:
                raise self.error(f"'{kind}' must be inside a loop")
            self.emit("jmp", self.loops[-1][0 if kind == "continue" else 1])

    def loop_body(self, body, continue_label, break_label):
        self.loops.append((continue_label, break_label))
        self.statement(body)
        self.loops.pop()

    def effect(self, node):
        """An expression whose value isn't used."""
        if node.kind == "incdec":
            self.incdec(node, keep_old=False)
        else:
            self.value(node)

    # Names

    def lookup(self, name, line):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        if name in self.globals:
            return self.globals[name]
        if name in self.functions or name in BUILTINS:
            raise self.error(f"'{name}' is a function; call it with ()", line)
        raise self.error(f"'{name}' is not declared", line)

    def scalar_address(self, node):
        symbol = self.lookup(node.name, node.line)
        if symbol.is_array:
            raise self.error(f"'{node.name}' is an array; use an element such as {node.name}[0]", node.line)
        return symbol.address

    def is_scalar(self, node):
        if node.kind != "var":
            return False
        return not self.lookup(node.name, node.line).is_array

    # Constants

    def fold(self, node):
        """The value of a constant expression, or None."""
        kind = node.kind
        if kind == "num":
            return node.value
        if kind == "unary":
            value = self.fold(node.operand)
            if value is None:
                return None
            return {"-": -value, "+": value, "~": ~value & 0xFF, "!": int(not value)}[node.op]
        if kind == "binary":
            left = self.fold(node.left)
            right = self.fold(node.right) if left is not None else None
            if right is None:
                return None
            op = node.op
            if op in ("/", "%") and right == 0:
                raise self.error("division by zero", node.line)
            return {
                "+": lambda: left + right, "-": lambda: left - right, "*": lambda: left * right,
                "/": lambda: left // right, "%": lambda: left % right, "&": lambda: left & right,
                "|": lambda: left | right, "^": lambda: left ^ right, "<<": lambda: left << right,
                ">>": lambda: left >> right, "==": lambda: int(left == right), "!=": lambda: int(left != right),
                "<": lambda: int(left < right), ">": lambda: int(left > right), "<=": lambda: int(left <= right),
                ">=": lambda: int(left >= right), "&&": lambda: int(bool(left and right)),
                "||": lambda: int(bool(left or right)),
            }[op]()
        if kind == "ternary":
            condition = self.fold(node.condition)
            if condition is None:
                return None
            return self.fold(node.yes if condition else node.no)
        return None

    # Expressions: the value ends up in A

    def value(self, node):
        constant = self.fold(node)
        if constant is not None:
            self.emit("mvi", "A", self.byte(constant, node.line))
            return
        kind = node.kind
        if kind == "var":
            self.emit("ld", "A", _address(self.scalar_address(node)))
        elif kind == "str":
            raise self.error('a string can only be printed, with puts("...")', node.line)
        elif kind == "index":
            address = self.element(node)
            if address is not None:
                self.emit("ld", "A", _address(address))
            else:
                self.emit("ldx", "A")
        elif kind == "call":
            self.call(node)
        elif kind == "unary":
            if node.op == "!":
                self.bool_value(node)
                return
            self.value(node.operand)
            if node.op == "-":
                self.emit("mov", "B", "A")
                self.emit("mvi", "A", 0)
                self.emit("sub", "A", "B")
            elif node.op == "~":
                self.emit("inv", "A")
        elif kind == "binary":
            if node.op in COMPARISONS or node.op in ("&&", "||"):
                self.bool_value(node)
            else:
                self.arithmetic(node)
        elif kind == "ternary":
            otherwise, end = self.new_label("else"), self.new_label("end")
            self.jump(node.condition, otherwise, False)
            self.value(node.yes)
            self.emit("jmp", end)
            self.label(otherwise)
            self.value(node.no)
            self.label(end)
        elif kind == "assign":
            self.assign(node)
        elif kind == "incdec":
            self.incdec(node, keep_old=not node.prefix)
        elif kind == "init_list":
            raise self.error("braces can only give an array its values", node.line)

    def arithmetic(self, node):
        op, left, right = node.op, node.left, node.right
        constant = self.fold(right)
        if constant is None and op in COMMUTATIVE:
            constant = self.fold(left)
            if constant is not None:
                left, right = right, left
        if constant is not None:
            self.value(left)
            self.apply_constant(op, self.byte(constant, right.line), right.line)
        elif op in MEMORY_FORMS and self.is_scalar(right):
            self.value(left)
            self.emit(MEMORY_FORMS[op], "A", _address(self.scalar_address(right)))
        else:
            self.value(left)
            self.emit("push", "A")
            self.value(right)
            self.emit("mov", "B", "A")
            self.emit("pop", "A")
            self.apply_registers(op)

    def apply_constant(self, op, constant, line):
        """A = A op constant."""
        if op in ("/", "%") and constant == 0:
            raise self.error("division by zero", line)
        if op == "%":
            if constant & (constant - 1) == 0:
                self.emit("andi", "A", constant - 1)
            else:
                self.emit("mvi", "B", constant)
                self.apply_registers("%")
            return
        self.emit(IMMEDIATE_FORMS[op], "A", constant)

    def apply_registers(self, op):
        """A = A op B."""
        if op in REGISTER_FORMS:
            self.emit(REGISTER_FORMS[op], "A", "B")
        elif op == "%":
            self.emit("push", "A")
            self.emit("div", "A", "B")
            self.emit("mul", "A", "B")
            self.emit("mov", "B", "A")
            self.emit("pop", "A")
            self.emit("sub", "A", "B")
        else:  # shift by B bits
            top, done = self.new_label("shift"), self.new_label("shifted")
            self.label(top)
            self.emit("jz", "B", done)
            self.emit("shl" if op == "<<" else "shr", "A", 1)
            self.emit("dec", "B")
            self.emit("jmp", top)
            self.label(done)

    def bool_value(self, node):
        false, end = self.new_label("false"), self.new_label("end")
        self.jump(node, false, False)
        self.emit("mvi", "A", 1)
        self.emit("jmp", end)
        self.label(false)
        self.emit("mvi", "A", 0)
        self.label(end)

    def jump(self, node, target, when):
        """Jump to target if the truth of node equals when; otherwise fall through."""
        constant = self.fold(node)
        if constant is not None:
            if bool(constant) == when:
                self.emit("jmp", target)
            return
        if node.kind == "unary" and node.op == "!":
            self.jump(node.operand, target, not when)
            return
        if node.kind == "binary" and node.op in ("&&", "||"):
            both = node.op == "&&"
            if when != both:
                # && that should jump when false, or || that should jump when true: either side decides
                self.jump(node.left, target, when)
                self.jump(node.right, target, when)
            else:
                skip = self.new_label("skip")
                self.jump(node.left, skip, not when)
                self.jump(node.right, target, when)
                self.label(skip)
            return
        if node.kind == "binary" and node.op in COMPARISONS:
            self.compare(node, target, when)
            return
        self.value(node)
        self.emit("jnz" if when else "jz", "A", target)

    def compare(self, node, target, when):
        op, left, right = node.op, node.left, node.right
        constant = self.fold(right)
        if constant is None:
            constant = self.fold(left)
            if constant is not None:
                left, right, op = right, left, MIRRORED[op]
        if constant is not None:
            constant = self.byte(constant, right.line)
            self.value(left)
            if op in ("==", "!="):
                if constant:
                    self.emit("subi", "A", constant)
                self.emit("jz" if (op == "==") == when else "jnz", "A", target)
            else:
                self.emit(CONSTANT_JUMPS[op if when else NEGATED[op]], "A", constant, target)
            return
        self.value(left)
        if self.is_scalar(right):
            self.emit("ld", "B", _address(self.scalar_address(right)))
        else:
            self.emit("push", "A")
            self.value(right)
            self.emit("mov", "B", "A")
            self.emit("pop", "A")
        if op in ("==", "!="):
            self.emit("sub", "A", "B")
            self.emit("jz" if (op == "==") == when else "jnz", "A", target)
            return
        # cmp sets carry when its first operand is below the second
        if op in ("<", ">="):
            self.emit("cmp", "A", "B")
            carry_means_true = op == "<"
        else:
            self.emit("cmp", "B", "A")
            carry_means_true = op == ">"
        self.emit("jc" if carry_means_true == when else "jnc", target)

    # Memory

    def element(self, node):
        """The address of array element node when its index is a constant; otherwise X:Y is set to it."""
        symbol = self.lookup(node.name, node.line)
        if not symbol.is_array:
            raise self.error(f"'{node.name}' isn't an array", node.line)
        index = self.fold(node.index)
        if index is not None:
            if not 0 <= index < symbol.size:
                raise self.error(f"index {index} is outside {node.name}[{symbol.size}]", node.line)
            return symbol.address + index
        self.value(node.index)
        self.address_from_a(symbol.address)
        return None

    def address_from_a(self, base):
        """X:Y = base + A."""
        high, low = base >> 8, base & 0xFF
        if low:
            self.emit("addi", "A", low)
        self.emit("mov", "Y", "A")
        self.emit("mvi", "X", high)
        if low:
            done = self.new_label("addressed")
            self.emit("jnc", done)
            self.emit("inc", "X")
            self.label(done)

    def target_address(self, target):
        """The fixed address of an assignment target, or None for an array element with a computed index."""
        if target.kind == "var":
            return self.scalar_address(target)
        if self.fold(target.index) is not None:
            return self.element(target)
        return None

    def memory_address(self, node):
        """For peek and poke: a constant address, or None with X:Y set to the computed address."""
        constant = self.fold(node)
        if constant is not None:
            if not 0 <= constant <= 0xFFFF:
                raise self.error(f"address {constant} is outside 0 to 0xFFFF", node.line)
            return constant
        if node.kind == "binary" and node.op == "+":
            for base, index in ((node.left, node.right), (node.right, node.left)):
                base_value = self.fold(base)
                if base_value is not None:
                    if not 0 <= base_value <= 0xFFFF:
                        raise self.error(f"address {base_value} is outside 0 to 0xFFFF", node.line)
                    self.value(index)
                    self.address_from_a(base_value)
                    return None
        self.value(node)
        self.address_from_a(0)
        return None

    def assign(self, node):
        op, target = node.op, node.target
        address = self.target_address(target)
        operator = op[:-1]
        if address is not None:
            if op == "=":
                self.value(node.value)
            else:
                constant = self.fold(node.value)
                if constant is not None:
                    self.emit("ld", "A", _address(address))
                    self.apply_constant(operator, self.byte(constant, node.value.line), node.value.line)
                elif operator in MEMORY_FORMS and self.is_scalar(node.value):
                    self.emit("ld", "A", _address(address))
                    self.emit(MEMORY_FORMS[operator], "A", _address(self.scalar_address(node.value)))
                else:
                    self.value(node.value)
                    self.emit("mov", "B", "A")
                    self.emit("ld", "A", _address(address))
                    self.apply_registers(operator)
            self.emit("st", "A", _address(address))
            return
        self.value(node.value)
        self.emit("push", "A")
        self.element(target)
        if op == "=":
            self.emit("pop", "A")
        else:
            self.emit("ldx", "A")
            self.emit("pop", "B")
            self.apply_registers(operator)
        self.emit("stx", "A")

    def incdec(self, node, keep_old):
        step, undo = ("inc", "dec") if node.op == "++" else ("dec", "inc")
        address = self.target_address(node.target)
        if address is not None:
            self.emit("ld", "A", _address(address))
            self.emit(step, "A")
            self.emit("st", "A", _address(address))
        else:
            self.element(node.target)
            self.emit("ldx", "A")
            self.emit(step, "A")
            self.emit("stx", "A")
        if keep_old:
            self.emit(undo, "A")

    # Calls

    def call(self, node):
        name, args = node.name, node.args
        if name in BUILTINS:
            self.builtin(node)
            return
        function = self.functions.get(name)
        if function is None:
            for scope in (*self.scopes, self.globals):
                if name in scope:
                    raise self.error(f"'{name}' is a variable, not a function", node.line)
            raise self.error(f"'{name}' is not declared", node.line)
        if len(args) != len(function.params):
            raise self.error(f"{name}() takes {self._count(len(function.params))}, got {len(args)}", node.line)
        if len(args) == 1:
            self.value(args[0])
            self.emit("mov", PARAM_REGISTERS[0], "A")
        elif args:
            for arg in args:
                self.value(arg)
                self.emit("push", "A")
            for register in reversed(PARAM_REGISTERS[:len(args)]):
                self.emit("pop", register)
        self.emit("call", function.label)

    @staticmethod
    def _count(n):
        return f"{n} argument" if n == 1 else f"{n} arguments"

    def builtin(self, node):
        name, args = node.name, node.args
        if len(args) != BUILTINS[name]:
            raise self.error(f"{name}() takes {self._count(BUILTINS[name])}, got {len(args)}", node.line)
        if name == "print":
            self.value(args[0])
            self.emit("out", "A")
        elif name == "putchar":
            self.value(args[0])
            self.emit("outc", "A")
        elif name == "puts":
            if args[0].kind != "str":
                raise self.error('puts() prints a string in quotes, like puts("HELLO")', node.line)
            loaded = None
            for code in args[0].codes + [10]:
                if code != loaded:
                    self.emit("mvi", "A", code)
                    loaded = code
                self.emit("outc", "A")
        elif name == "keys":
            self.emit("ld", "A", _address(KEYS_ADDRESS))
        elif name == "keychar":
            self.emit("ld", "A", _address(CHAR_KEY_ADDRESS))
        elif name == "rand":
            self.emit("ld", "A", _address(RANDOM_ADDRESS))
        elif name == "frame":
            self.emit("frame")
        elif name == "halt":
            self.emit("hlt")
        elif name == "plot":
            x, y, color = args
            self.value(color)
            self.emit("push", "A")
            self.value(x)
            self.emit("push", "A")
            self.value(y)
            self.screen_address()
            self.emit("pop", "A")
            self.emit("stx", "A")
        elif name == "pixel":
            x, y = args
            self.value(x)
            self.emit("push", "A")
            self.value(y)
            self.screen_address()
            self.emit("ldx", "A")
        elif name == "clear":
            self.value(args[0])
            self.emit("mvi", "X", SCREEN_HIGH_BYTE)
            self.emit("mvi", "Y", 0)
            top = self.new_label("clear")
            self.label(top)
            self.emit("stx", "A")
            self.emit("inxy")
            self.emit("jb", "X", SCREEN_END_HIGH_BYTE, top)
        elif name == "peek":
            address = self.memory_address(args[0])
            if address is not None:
                self.emit("ld", "A", _address(address))
            else:
                self.emit("ldx", "A")
        elif name == "poke":
            destination, value = args
            constant = self.fold(destination)
            if constant is not None:
                address = self.memory_address(destination)
                self.value(value)
                self.emit("st", "A", _address(address))
            else:
                self.value(value)
                self.emit("push", "A")
                self.memory_address(destination)
                self.emit("pop", "A")
                self.emit("stx", "A")

    def screen_address(self):
        """X:Y = the screen address of pixel (x, y), with y in A and x on the stack. Both wrap at 32."""
        self.emit("andi", "A", 31)
        self.emit("mov", "X", "A")
        self.emit("shr", "X", 3)
        self.emit("addi", "X", SCREEN_HIGH_BYTE)
        self.emit("shl", "A", 5)
        self.emit("pop", "B")
        self.emit("andi", "B", 31)
        self.emit("ord", "A", "B")
        self.emit("mov", "Y", "A")
