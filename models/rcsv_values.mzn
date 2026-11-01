% 2015 section 3, RCSV specialized to tables without spans.
% The API's hard lower width bound must be added to the paper's width union.
array[1..n] of set of int: width_values = [
    {lo[j]} union {sw[k] | d in 1..cells, k in first[d]..last[d]
        where cell_col[d] = j /\ sw[k] >= lo[j] /\ sw[k] <= hi[j]}
    | j in 1..n];
array[1..m] of set of int: height_values = [
    {sh[k] | d in 1..cells, k in first[d]..last[d]
        where cell_row[d] = i /\ sh[k] <= row_upper[i]}
    | i in 1..m];
