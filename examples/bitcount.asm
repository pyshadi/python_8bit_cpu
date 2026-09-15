; bitcount: count the 1 bits in B using shifts and the carry flag
        mvi, B, 0b10110110
        mvi, C, 0        ; bits counted
        mvi, D, 8        ; bits left to check
loop:   shr, B, 1        ; the lowest bit moves into carry
        jnc, skip
        inc, C
skip:   dec, D
        jnz, D, loop
        out, C           ; print the count
        hlt
