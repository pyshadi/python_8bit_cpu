; swap: exchange B and C using the stack inside a subroutine
        mvi, B, 7
        mvi, C, 42
        call, swap
        hlt

swap:   push, B          ; the return address is below these on the stack
        push, C
        pop, B           ; last in, first out: B gets C's value
        pop, C
        ret
