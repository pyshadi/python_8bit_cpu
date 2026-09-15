; multiply: 7 x 6 by repeated addition, result in D and RAM[0x0100]
        mvi, B, 7        ; multiplicand
        mvi, C, 6        ; multiplier, counts down
        mvi, D, 0        ; running total
loop:   jz, C, done
        add, D, B        ; A = D + B
        mov, D, A
        dec, C
        jmp, loop
done:   st, D, 0x0100
        hlt
