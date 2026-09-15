; keys: move a dot around the screen with the arrow keys (click the Display first)
        mvi, C, 16          ; x
        mvi, D, 16          ; y
main:   call, locate        ; erase the dot at its old position
        mvi, A, 0
        stx, A
        ld, B, 0xFF00       ; keys: 1 up, 2 down, 4 left, 8 right
        mov, E, B
        andi, E, 1
        jz, E, not_up
        dec, D
not_up: mov, E, B
        andi, E, 2
        jz, E, not_down
        inc, D
not_down: mov, E, B
        andi, E, 4
        jz, E, not_left
        dec, C
not_left: mov, E, B
        andi, E, 8
        jz, E, not_right
        inc, C
not_right: andi, C, 31      ; wrap around the edges
        andi, D, 31
        call, locate        ; draw the dot in brass
        mvi, A, 2
        stx, A
        frame
        jmp, main

; X:Y = F000 + y * 32 + x
locate: mov, Y, D
        shl, Y, 5
        ord, Y, C           ; A = Y | x
        mov, Y, A
        mov, X, D
        shr, X, 3
        addi, X, 0xF0
        ret
