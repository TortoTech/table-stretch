% Alternative standard (one-hot) configuration encoding in 2015 section 4.
include "common.mzn";
array[1..steps] of var 0..1: z;
constraint forall(d in 1..cells)(
    sum(k in first[d]..last[d])(z[k]) = 1 /\
    w[cell_col[d]] >= sum(k in first[d]..last[d])(sw[k]*z[k]) /\
    h[cell_row[d]] >= sum(k in first[d]..last[d])(sh[k]*z[k])
);
solve minimize total_height;
