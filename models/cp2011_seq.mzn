% 2011 section 6: select the unfixed cell with the smallest remaining
% configuration height, and try that height first. Modern FlatZinc adaptation.
include "common.mzn";
array[1..cells] of var 1..steps: config;
array[1..cells] of var 0..max(sh): cell_height;
constraint forall(d in 1..cells)(
    config[d] in ({first[d]} union
        {k | k in first[d]+1..last[d] where sh[k] < sh[k-1]}) /\
    cell_height[d] = sh[config[d]] /\
    w[cell_col[d]] >= sw[config[d]] /\ h[cell_row[d]] >= cell_height[d]
);
% Removing dominated, equal-height configurations makes height identify a
% unique configuration. Tie order is our column-major input order.
solve :: int_search(cell_height, smallest, indomain_min, complete)
    minimize total_height;
