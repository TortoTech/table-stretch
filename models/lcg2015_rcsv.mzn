% Cell-free + RCSV, 2015 cpcf's simple-cell specialization.
include "lcg2015.mzn";
include "rcsv_values.mzn";
constraint forall(j in 1..n)(w[j] in width_values[j]);
constraint forall(i in 1..m)(h[i] in height_values[i]);
% Search is selected by the caller (pure VSIDS), not the inherited width
% annotation. Historical Chuffed version/search defaults are not reproduced.
