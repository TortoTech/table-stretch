% Shared simple-table model. Integer dimensions, same bounds as the Rust core.
int: n; int: m; int: budget; int: cells; int: steps;
array[1..n] of int: lo; array[1..n] of int: hi;
array[1..m] of int: row_upper;
array[1..cells] of int: first; array[1..cells] of int: last;
array[1..cells] of int: cell_row; array[1..cells] of int: cell_col;
array[1..steps] of int: sw; array[1..steps] of int: sh;
array[1..n] of var 0..budget: w;
array[1..m] of var 0..max(row_upper): h;
constraint forall(j in 1..n)(w[j] >= lo[j] /\ w[j] <= hi[j]);
constraint forall(i in 1..m)(h[i] <= row_upper[i]);
constraint sum(w) <= budget;
var int: total_height = sum(h);
output ["{\"widths\":", show(w), ",\"heights\":", show(h),
        ",\"height\":", show(total_height), "}"];
