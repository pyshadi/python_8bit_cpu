; countdown: count A down from 10 to 0
        mvi, A, 10
loop:   dec, A
        jnz, A, loop
        hlt
