; pattern: fill the 32x32 screen with diagonal color stripes, then halt
        mvi, X, 0xF0     ; X:Y = F000, the first pixel
        mvi, Y, 0
        mvi, C, 0        ; x
        mvi, D, 0        ; y
loop:   add, C, D        ; A = x + y
        andi, A, 3       ; one of the four colors
        stx, A           ; draw the pixel at X:Y
        inxy             ; next pixel
        inc, C
        jb, C, 32, loop
        mvi, C, 0
        inc, D
        jb, D, 32, loop
        frame
        hlt
