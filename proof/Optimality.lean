import Std

/- Abstract exact-search kernel. No mathlib, custom axioms, or admitted proofs.
   Natural numbers model checked Rust arithmetic. See docs/proof.md for the
   refinement boundary (profiles, Rust execution and stretch implementation). -/
namespace TableStretch

structure State where
  width : Nat
  height : Nat → Nat

def Dom (a b : State) : Prop :=
  a.width ≤ b.width ∧ ∀ r, a.height r ≤ b.height r

theorem dom_refl (a : State) : Dom a a := ⟨Nat.le_refl _, fun _ => Nat.le_refl _⟩

theorem dom_trans {a b c : State} (ab : Dom a b) (bc : Dom b c) : Dom a c :=
  ⟨Nat.le_trans ab.1 bc.1, fun r => Nat.le_trans (ab.2 r) (bc.2 r)⟩

def extend (a c : State) : State :=
  ⟨a.width + c.width, fun r => max (a.height r) (c.height r)⟩

theorem extend_mono {a b : State} (h : Dom a b) (c : State) :
    Dom (extend a c) (extend b c) := by
  constructor
  · exact Nat.add_le_add_right h.1 _
  · intro r
    exact Nat.max_le_of_le_of_le
      (Nat.le_trans (h.2 r) (Nat.le_max_left _ _)) (Nat.le_max_right _ _)

def cost (a : State) : Nat → Nat
  | 0 => 0
  | n + 1 => cost a n + a.height n

theorem cost_mono {a b : State} (h : Dom a b) (n : Nat) : cost a n ≤ cost b n := by
  induction n with
  | zero => exact Nat.le_refl _
  | succ n ih => exact Nat.add_le_add ih (h.2 n)

def Covers (frontier all : List State) : Prop :=
  ∀ s ∈ all, ∃ f ∈ frontier, Dom f s

theorem covers_refl (xs : List State) : Covers xs xs :=
  fun s hs => ⟨s, hs, dom_refl s⟩

theorem covers_trans {a b c : List State} (ab : Covers a b) (bc : Covers b c) :
    Covers a c := by
  intro s hs
  obtain ⟨y, hy, dys⟩ := bc s hs
  obtain ⟨x, hx, dxy⟩ := ab y hy
  exact ⟨x, hx, dom_trans dxy dys⟩

noncomputable def insert (x : State) (fs : List State) : List State := by
  classical
  exact if ∃ y ∈ fs, Dom y x then fs else x :: fs.filter (fun y => ¬ Dom x y)

theorem insert_covers (x : State) (fs : List State) : Covers (insert x fs) (x :: fs) := by
  classical
  unfold insert
  split
  · rename_i h
    intro s hs
    rcases List.mem_cons.mp hs with heq | hs
    · subst s
      exact h
    · exact ⟨s, hs, dom_refl s⟩
  · intro s hs
    rcases List.mem_cons.mp hs with heq | hs
    · subst s
      exact ⟨x, List.mem_cons_self, dom_refl x⟩
    · by_cases h : Dom x s
      · exact ⟨x, List.mem_cons_self, h⟩
      · refine ⟨s, List.mem_cons_of_mem x ?_, dom_refl s⟩
        simp only [List.mem_filter, decide_eq_true_eq]
        exact ⟨hs, h⟩

noncomputable def prune : List State → List State
  | [] => []
  | x :: xs => insert x (prune xs)

theorem prune_covers (xs : List State) : Covers (prune xs) xs := by
  induction xs with
  | nil => exact covers_refl []
  | cons x xs ih =>
    apply covers_trans (insert_covers x (prune xs))
    intro s hs
    rcases List.mem_cons.mp hs with heq | hs
    · subst s
      exact ⟨x, List.mem_cons_self, dom_refl x⟩
    · obtain ⟨f, hf, hdom⟩ := ih s hs
      exact ⟨f, List.mem_cons_of_mem x hf, hdom⟩

theorem prune_subset (xs : List State) : ∀ s ∈ prune xs, s ∈ xs := by
  classical
  induction xs with
  | nil => simp [prune]
  | cons x xs ih =>
    intro s hs
    simp only [prune, insert] at hs
    split at hs
    · exact List.mem_cons_of_mem x (ih s hs)
    · rcases List.mem_cons.mp hs with heq | hs
      · exact List.mem_cons.mpr (Or.inl heq)
      · exact List.mem_cons_of_mem x (ih s (List.mem_filter.mp hs).1)

def expand (budget : Nat) (fs cs : List State) : List State :=
  (fs.flatMap fun f => cs.map (extend f)).filter (fun s => s.width ≤ budget)

theorem expand_covers (budget : Nat) (cs : List State) {fs xs : List State}
    (h : Covers fs xs) : Covers (expand budget fs cs) (expand budget xs cs) := by
  intro s hs
  obtain ⟨hs, hb⟩ := List.mem_filter.mp hs
  have hb : s.width ≤ budget := by simpa using hb
  obtain ⟨x, hx, hc⟩ := List.mem_flatMap.mp hs
  obtain ⟨c, hcmem, heq⟩ := List.mem_map.mp hc
  subst s
  obtain ⟨f, hf, hd⟩ := h x hx
  have he := extend_mono hd c
  refine ⟨extend f c, ?_, he⟩
  apply List.mem_filter.mpr
  constructor
  · exact List.mem_flatMap.mpr ⟨f, hf, List.mem_map.mpr ⟨c, hcmem, rfl⟩⟩
  · simpa using Nat.le_trans he.1 hb

noncomputable def run (budget : Nat) : List (List State) → List State → List State
  | [], fs => fs
  | cs :: rest, fs => run budget rest (prune (expand budget fs cs))

def exhaustive (budget : Nat) : List (List State) → List State → List State
  | [], fs => fs
  | cs :: rest, fs => exhaustive budget rest (expand budget fs cs)

theorem expand_subset (budget : Nat) (cs : List State) {fs xs : List State}
    (h : ∀ s ∈ fs, s ∈ xs) :
    ∀ s ∈ expand budget fs cs, s ∈ expand budget xs cs := by
  intro s hs
  obtain ⟨hm, hb⟩ := List.mem_filter.mp hs
  obtain ⟨f, hf, hc⟩ := List.mem_flatMap.mp hm
  exact List.mem_filter.mpr ⟨List.mem_flatMap.mpr ⟨f, h f hf, hc⟩, hb⟩

theorem run_subset (budget : Nat) (cols : List (List State))
    {fs xs : List State} (h : ∀ s ∈ fs, s ∈ xs) :
    ∀ s ∈ run budget cols fs, s ∈ exhaustive budget cols xs := by
  induction cols generalizing fs xs with
  | nil => exact h
  | cons cs rest ih =>
    apply ih
    intro s hs
    exact expand_subset budget cs h s (prune_subset _ s hs)

theorem run_covers (budget : Nat) (cols : List (List State))
    {fs xs : List State} (h : Covers fs xs) :
    Covers (run budget cols fs) (exhaustive budget cols xs) := by
  induction cols generalizing fs xs with
  | nil => exact h
  | cons cs rest ih =>
    exact ih (covers_trans (prune_covers _) (expand_covers budget cs h))

/- Selecting the smallest objective in the retained frontier is globally
   optimal over exhaustive candidate layouts, not just locally optimal. -/
theorem global_optimality (budget rows : Nat) (cols : List (List State))
    (initial : List State) (best : State)
    (hbest : best ∈ run budget cols initial)
    (hmin : ∀ f ∈ run budget cols initial, cost best rows ≤ cost f rows) :
    best ∈ exhaustive budget cols initial ∧
    ∀ s ∈ exhaustive budget cols initial, cost best rows ≤ cost s rows := by
  constructor
  · exact run_subset budget cols (fun _ h => h) best hbest
  intro s hs
  obtain ⟨f, hf, hd⟩ := run_covers budget cols (covers_refl initial) s hs
  exact Nat.le_trans (hmin f hf) (cost_mono hd rows)

/- Stretching any globally optimal feasible layout, without increasing any
   row height and while remaining feasible, preserves the optimal value. -/
theorem stretch_preserves_optimum (rows : Nat) (feasible : State → Prop)
    (best stretched : State)
    (opt : ∀ s, feasible s → cost best rows ≤ cost s rows)
    (valid : feasible stretched)
    (nonincrease : ∀ r, stretched.height r ≤ best.height r) :
    cost stretched rows = cost best rows := by
  have upper : cost stretched rows ≤ cost best rows := by
    clear opt valid
    induction rows with
    | zero => exact Nat.le_refl _
    | succ n ih => exact Nat.add_le_add ih (nonincrease n)
  exact Nat.le_antisymm upper (opt stretched valid)

#print axioms global_optimality
#print axioms stretch_preserves_optimum

/- Optimized-search lemmas. These verify the abstract transformations, not a
   line-by-line refinement of the Rust arena or the arithmetic lower bounds. -/
theorem height_cost_mono {a b : State}
    (h : ∀ r, a.height r ≤ b.height r) (rows : Nat) : cost a rows ≤ cost b rows := by
  induction rows with
  | zero => exact Nat.le_refl _
  | succ n ih => exact Nat.add_le_add ih (h n)

theorem terminal_column_optimal (baseState : State) (profile : Nat → Nat → Nat)
    (cap budget w rows : Nat) (hw : w ≤ cap) (fits : baseState.width + w ≤ budget)
    (anti : ∀ x y, x ≤ y → ∀ r, profile y r ≤ profile x r) :
    cost (extend baseState ⟨min cap (budget - baseState.width),
      profile (min cap (budget - baseState.width))⟩) rows ≤
    cost (extend baseState ⟨w, profile w⟩) rows := by
  have hmax : w ≤ min cap (budget - baseState.width) := by omega
  apply height_cost_mono
  intro r
  exact Nat.max_le_of_le_of_le (Nat.le_max_left _ _)
    (Nat.le_trans (anti _ _ hmax r) (Nat.le_max_right _ _))

theorem lower_bound_pruning_safe (lower upper : Nat) (rows : Nat)
    (completion : State) (valid : lower ≤ cost completion rows)
    (cut : upper ≤ lower) : upper ≤ cost completion rows :=
  Nat.le_trans cut valid

/- Generic finite branch-and-bound minimum: each job represents a subtree
   with exact optimum `value` and a certified lower bound. The seed is a
   retained feasible incumbent. Equal-bound pruning preserves one optimum. -/
def boundedMinimum {α : Type} (lower value : α → Nat) : List α → Nat → Nat
  | [], upper => upper
  | x :: xs, upper =>
    if upper ≤ lower x then boundedMinimum lower value xs upper
    else boundedMinimum lower value xs (min upper (value x))

theorem bounded_minimum_correct {α : Type} (lower value : α → Nat)
    (valid : ∀ x, lower x ≤ value x) (jobs : List α) (upper : Nat) :
    (boundedMinimum lower value jobs upper = upper ∨
      ∃ x ∈ jobs, boundedMinimum lower value jobs upper = value x) ∧
    boundedMinimum lower value jobs upper ≤ upper ∧
    ∀ x ∈ jobs, boundedMinimum lower value jobs upper ≤ value x := by
  induction jobs generalizing upper with
  | nil => simp [boundedMinimum]
  | cons x xs ih =>
    simp only [boundedMinimum]
    split
    · rename_i cut
      obtain ⟨feasible, hu, hall⟩ := ih upper
      refine ⟨?_, hu, ?_⟩
      · rcases feasible with h | ⟨y, hy, heq⟩
        · exact Or.inl h
        · exact Or.inr ⟨y, List.mem_cons_of_mem _ hy, heq⟩
      · intro y hy
        rcases List.mem_cons.mp hy with heq | hy
        · subst y
          exact Nat.le_trans hu (Nat.le_trans cut (valid x))
        · exact hall y hy
    · obtain ⟨feasible, hu, hall⟩ := ih (min upper (value x))
      refine ⟨?_, Nat.le_trans hu (Nat.min_le_left _ _), ?_⟩
      · rcases feasible with h | ⟨y, hy, heq⟩
        · by_cases hux : upper ≤ value x
          · exact Or.inl (h.trans (Nat.min_eq_left hux))
          · exact Or.inr ⟨x, List.mem_cons_self,
              h.trans (Nat.min_eq_right (Nat.le_of_lt (Nat.lt_of_not_ge hux)))⟩
        · exact Or.inr ⟨y, List.mem_cons_of_mem _ hy, heq⟩
      · intro y hy
        rcases List.mem_cons.mp hy with heq | hy
        · subst y
          exact Nat.le_trans hu (Nat.min_le_right _ _)
        · exact hall y hy

/- Global invariant after combining Pareto coverage with bound pruning:
   every full layout is either covered by a retained completion or cannot
   beat the feasible incumbent. The returned minimum is globally optimal. -/
theorem bounded_global_optimality (rows : Nat) (feasible : State → Prop)
    (frontier : List State) (incumbent best : State)
    (valid : feasible best)
    (cover : ∀ s, feasible s → cost incumbent rows ≤ cost s rows ∨
      ∃ f ∈ frontier, cost f rows ≤ cost s rows)
    (seed : cost best rows ≤ cost incumbent rows)
    (minimal : ∀ f ∈ frontier, cost best rows ≤ cost f rows) :
    feasible best ∧ ∀ s, feasible s → cost best rows ≤ cost s rows := by
  refine ⟨valid, ?_⟩
  intro s hs
  rcases cover s hs with h | ⟨f, hf, hfs⟩
  · exact Nat.le_trans seed h
  · exact Nat.le_trans (minimal f hf) hfs

#print axioms terminal_column_optimal
#print axioms lower_bound_pruning_safe
#print axioms bounded_minimum_correct
#print axioms bounded_global_optimality
end TableStretch
