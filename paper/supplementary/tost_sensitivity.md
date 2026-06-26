# Post-hoc Agresti-Caffo TOST sensitivity analysis

Equivalence margin ±0.05; decision threshold Holm-adjusted p < α = 0.05.
Raw = pre-registered Wald-unpooled TOST. AC = Agresti-Caffo-adjusted (add one success and one failure per arm). † marks pairs with an arm at the 0/1 boundary.

## CLEAN

| Pair | rec1 | rec2 | Raw TOST p (Holm) | AC TOST p (Holm) | Boundary |
|------|------|------|-------------------|------------------|----------|
| Z01 vs Z02 | 0.990 | 0.995 | 7.96e-14 (3.184e-13) | 6.238e-11 (2.495e-10) |  |
| Z01 vs Z03 | 0.990 | 0.992 | 2.824e-13 (3.184e-13) | 7.803e-11 (2.495e-10) |  |
| Z01 vs Z04 | 0.990 | 0.995 | 7.96e-14 (3.184e-13) | 6.238e-11 (2.495e-10) |  |
| Z01 vs Z05 | 0.990 | 0.995 | 7.96e-14 (3.184e-13) | 6.238e-11 (2.495e-10) |  |
| Z02 vs Z03 | 0.995 | 0.992 | 0 (0) | 2.288e-13 (1.601e-12) |  |
| Z02 vs Z04 | 0.995 | 0.995 | 0 (0) | 1.11e-16 (1.11e-15) |  |
| Z02 vs Z05 | 0.995 | 0.995 | 0 (0) | 1.11e-16 (1.11e-15) |  |
| Z03 vs Z04 | 0.992 | 0.995 | 0 (0) | 2.287e-13 (1.601e-12) |  |
| Z03 vs Z05 | 0.992 | 0.995 | 0 (0) | 2.287e-13 (1.601e-12) |  |
| Z04 vs Z05 | 0.995 | 0.995 | 0 (0) | 1.11e-16 (1.11e-15) |  |

H1 under raw test: **PASS** · under AC test: **PASS**

## ROGUE

| Pair | rec1 | rec2 | Raw TOST p (Holm) | AC TOST p (Holm) | Boundary |
|------|------|------|-------------------|------------------|----------|
| Z01 vs Z02 | 0.990 | 0.992 | 0 (0) | 0 (0) |  |
| Z01 vs Z03 | 0.990 | 0.979 | 2.113e-10 (6.34e-10) | 8.081e-10 (2.424e-09) |  |
| Z01 vs Z04 | 0.990 | 0.987 | 0 (0) | 0 (0) |  |
| Z01 vs Z05 | 0.990 | 0.990 | 0 (0) | 0 (0) |  |
| Z02 vs Z03 | 0.992 | 0.979 | 5.625e-10 (6.34e-10) | 2.247e-09 (2.424e-09) |  |
| Z02 vs Z04 | 0.992 | 0.987 | 0 (0) | 0 (0) |  |
| Z02 vs Z05 | 0.992 | 0.990 | 0 (0) | 0 (0) |  |
| Z03 vs Z04 | 0.979 | 0.987 | 7.81e-11 (3.124e-10) | 2.88e-10 (1.152e-09) |  |
| Z03 vs Z05 | 0.979 | 0.990 | 2.113e-10 (6.34e-10) | 8.081e-10 (2.424e-09) |  |
| Z04 vs Z05 | 0.987 | 0.990 | 0 (0) | 0 (0) |  |

H1 under raw test: **PASS** · under AC test: **PASS**

---

**Overall:** H1 raw = PASS, H1 AC = PASS, robustness HOLDS.