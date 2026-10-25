# Proposed issue: Reconcile phase status and record human acceptance of merged evidence

Status: proposed, not created or assigned in GitHub. Agent roles are proposed ownership, not GitHub usernames or launched workers.

Phase tasks: #1 “Separate missing price data from defensive sell signals”, “Compare strategies against buy-and-hold and cash”, “Model fees and slippage”; #2 four implemented controls; #4 navigation, sections and P/L.

Owner: Project Manager (lead), human reviewer; Testing Agent supports.

Dependencies: This verification PR; no development prerequisite.

File ownership and conflict reservation: ROADMAP.md, research/roadmap_evidence.json, research/roadmap_verification.md and phase issue bodies. PM is sole writer of these files.

Acceptance criteria:

- [ ] Human verifies each of the ten implemented-pending-review tasks against linked code, relevant head/main CI, and stated limitations; record an explicit task-specific GitHub review/comment URL and identity.
- [ ] Confirm whether Phase 1's closed state was intentional; reconcile status only with human direction. Do not close any issue or infer completion from its state.
- [ ] Leave combined monthly/yearly and CSV/PDF tasks unchecked; update only individually accepted tasks after merge and CI.
- [ ] Run the evidence gate and regression suite; do not fabricate human metadata or auto-check issues.

Use a dedicated branch, link the parent phase issue and exact task, post a plan, and open a separate PR. Run the handbook unittest/compile checks and task-specific tests. Keep trading simulated; no strategy changes, brokerage connections, real orders, automatic merge, issue closure or unchecked-to-checked transitions without merged CI and human acceptance.
