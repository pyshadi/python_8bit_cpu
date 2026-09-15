; countdown: print A while counting down from 10 to 1
        mvi, A, 10
loop:   out, A
        dec, A
        jnz, A, loop
        hlt
