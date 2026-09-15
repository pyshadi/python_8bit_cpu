; swap: exchange B and C using the stack inside a subroutine
        mvi, B, 7
        mvi, C, 42
        call, swap
        out, B           ; prints 42
        out, C           ; prints 7
        hlt

swap:   push, B          ; the return address is below these on the stack
        push, C
        pop, B           ; last in, first out: B gets C's value
        pop, C
        ret
