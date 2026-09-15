; gcd: greatest common divisor of 48 and 18 by repeated subtraction, result in A
        mvi, A, 48
        mvi, B, 18
loop:   cmp, A, B
        jc, less         ; carry set: A < B
        sub, A, B        ; A = A - B
        jz, A, done      ; A was equal to B, so B is the answer
        jmp, loop
less:   mov, C, A        ; keep A
        sub, B, C        ; A = B - A
        mov, B, A
        mov, A, C
        jmp, loop
done:   mov, A, B
        hlt
