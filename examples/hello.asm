; hello: print HELLO, then the numbers 1 to 3
        mvi, A, 72       ; H
        outc, A
        mvi, A, 69       ; E
        outc, A
        mvi, A, 76       ; L
        outc, A
        outc, A
        mvi, A, 79       ; O
        outc, A
        mvi, A, 10       ; new line
        outc, A
        mvi, B, 1
loop:   out, B           ; prints the number and a new line
        inc, B
        jb, B, 4, loop
        hlt
