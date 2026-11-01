% Gange et al. 2011, section 4.1: cell-configuration element model.
% Gecode = ordinary CP; Chuffed = CP/SAT with lazy clause generation.
% Simple-cell specialization of the paper's model. Explicit width search.
include "common.mzn";
array[1..cells] of var 1..steps: config;
constraint forall(d in 1..cells)(
    config[d] >= first[d] /\ config[d] <= last[d] /\
    w[cell_col[d]] >= sw[config[d]] /\ h[cell_row[d]] >= sh[config[d]]
);
solve :: int_search(w, input_order, indomain_max, complete) minimize total_height;
