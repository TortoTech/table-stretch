% Bilauca et al. 2015, cell-free encoding (author manuscript section 3).
% Eliminate cell configuration variables for simple cells. Run with Chuffed.
include "common.mzn";
constraint forall(d in 1..cells)(
    w[cell_col[d]] >= sw[first[d]] /\ h[cell_row[d]] >= sh[last[d]] /\
    forall(k in first[d]..last[d]-1)(
        h[cell_row[d]] >= sh[k] \/ w[cell_col[d]] >= sw[k+1]
    )
);
solve :: int_search(w, input_order, indomain_max, complete) minimize total_height;
