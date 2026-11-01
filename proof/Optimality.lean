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
end TableStretch
