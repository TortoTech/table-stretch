% Cell-free + RCSV + unary row/column values, 2015 mipcf, no spans.
% Unlike per-cell unary/one-hot encodings, these selectors are shared by all
% cells on a row/column. No per-cell selectors or big-M disjunctions.
include "common.mzn";
include "rcsv_values.mzn";
array[int] of int: wc = [j | j in 1..n, v in width_values[j]];
array[int] of int: wv = [v | j in 1..n, v in width_values[j]];
array[int] of int: hr = [i | i in 1..m, v in height_values[i]];
array[int] of int: hv = [v | i in 1..m, v in height_values[i]];
array[1..n] of int: wf = [min(k in index_set(wc) where wc[k]=j)(k) | j in 1..n];
array[1..n] of int: wl = [max(k in index_set(wc) where wc[k]=j)(k) | j in 1..n];
array[1..m] of int: hf = [min(k in index_set(hr) where hr[k]=i)(k) | i in 1..m];
array[1..m] of int: hl = [max(k in index_set(hr) where hr[k]=i)(k) | i in 1..m];
array[index_set(wc)] of var 0..1: wb;
array[index_set(hr)] of var 0..1: hb;
constraint forall(j in 1..n)(wb[wf[j]]=1 /\
    forall(k in wf[j]+1..wl[j])(wb[k-1]>=wb[k]) /\
    w[j]=wv[wf[j]]+sum(k in wf[j]+1..wl[j])((wv[k]-wv[k-1])*wb[k]));
constraint forall(i in 1..m)(hb[hf[i]]=1 /\
    forall(k in hf[i]+1..hl[i])(hb[k-1]>=hb[k]) /\
    h[i]=hv[hf[i]]+sum(k in hf[i]+1..hl[i])((hv[k]-hv[k-1])*hb[k]));
function var int: width_ge(int: j, int: v) =
    if v <= wv[wf[j]] then 1 elseif v > wv[wl[j]] then 0
    else wb[min(k in wf[j]..wl[j] where wv[k]>=v)(k)] endif;
function var int: height_ge(int: i, int: v) =
    if v <= hv[hf[i]] then 1 elseif v > hv[hl[i]] then 0
    else hb[min(k in hf[i]..hl[i] where hv[k]>=v)(k)] endif;
constraint forall(d in 1..cells)(
    w[cell_col[d]] >= sw[first[d]] /\ h[cell_row[d]] >= sh[last[d]] /\
    forall(k in first[d]..last[d]-1)(
        height_ge(cell_row[d],sh[k])+width_ge(cell_col[d],sw[k+1])>=1)
);
solve minimize total_height;
