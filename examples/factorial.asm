; factorial: 5! = 120 by repeated multiplication, result in A
        mvi, B, 5        ; counts down to 1
        mvi, D, 1        ; running product
loop:   mul, D, B        ; A = D * B
        mov, D, A
        dec, B
        jnz, B, loop
        mov, A, D
        hlt
