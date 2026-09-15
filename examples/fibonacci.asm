; fibonacci: push the first ten terms
        mvi, A, 0      ; F(n-2)
        mvi, B, 1      ; F(n-1)
        mvi, C, 10     ; terms left
loop:   push, B
        call, next
        dec, C
        jnz, C, loop
        hlt

next:   mov, E, B   ; keep F(n-1)
        add, A, B   ; A = F(n)
        mov, B, A
        mov, A, E
        ret
