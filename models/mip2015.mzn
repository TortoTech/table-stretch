% Bilauca et al. 2015, section 4: unary configuration encoding.
% z is a prefix of ones per cell. Run using HiGHS (not the original CPLEX).
include "common.mzn";
array[1..steps] of var 0..1: z;
constraint forall(d in 1..cells)(
    z[first[d]] = 1 /\
    forall(k in first[d]+1..last[d])(z[k-1] >= z[k]) /\
    w[cell_col[d]] >= sw[first[d]] + sum(k in first[d]+1..last[d])((sw[k]-sw[k-1])*z[k]) /\
    h[cell_row[d]] >= sh[first[d]] + sum(k in first[d]+1..last[d])((sh[k]-sh[k-1])*z[k])
);
solve minimize total_height;
