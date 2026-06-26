#!/usr/bin/env python3
"""
Internal-consistency checker for PAPER.md results sections (§5.2-§5.6 + Appendix B).
Pure paper-vs-itself arithmetic; needs no run data. Complements validate_dashboard.py
(which checks dashboard-vs-itself). Source of truth = the §5.6.1 eight-cell table;
everything else (§5.2, §5.2.1, §5.4, §5.3.1) is derived from it and compared to what
the paper prints. A hallucinated/transcribed-wrong number breaks one of these ties.
"""

# --- §5.6.1 eight-cell (the atomic counts) -------------------------------------
# cols: clean_concur, clean_save, clean_break(FP), clean_both | rogue_concur, rogue_save, rogue_break(FN), rogue_both
EIGHT = {
 "Z01": (376,20,3,1, 632,159,0,8),
 "Z02": (353,45,2,0, 729,64,0,6),
 "Z03": (2,394,0,3,   782,0,17,0),
 "Z04": (397,1,2,0,   110,679,0,10),
 "Z05": (390,8,2,0,   637,154,0,8),
}
ANALYSED = {"Z01":1199,"Z02":1199,"Z03":1198,"Z04":1199,"Z05":1199}  # Appendix B

# --- reported values elsewhere in the paper ------------------------------------
REC = {  # §5.2 recovery clean%, rogue%, save%, break%
 "Z01":(99.0,99.0,95.2,0.30),"Z02":(99.5,99.2,94.8,0.18),"Z03":(99.2,97.9,99.2,2.12),
 "Z04":(99.5,98.7,98.6,0.39),"Z05":(99.5,99.0,95.3,0.19)}
FF = {  # §5.4 FPR%, FNR%
 "Z01":(1.0,1.0),"Z02":(0.5,0.8),"Z03":(0.8,2.1),"Z04":(0.5,1.3),"Z05":(0.5,1.0)}
STRAT = {  # §5.2.1 (n,N) for clean-correct, clean-wrong, rogue-correct, rogue-wrong
 "Z01":((376,379),(20,21),(632,632),(159,167)),
 "Z02":((353,355),(45,45),(729,729),(64,70)),
 "Z03":((2,2),(394,397),(782,799),(0,0)),
 "Z04":((397,399),(1,1),(110,110),(679,689)),
 "Z05":((390,392),(8,8),(637,637),(154,162))}
DELTA = {  # §5.3.1 clean_pp, rogue_pp
 ("Z01","Z02"):(-0.50,-0.25),("Z01","Z03"):(-0.25,1.13),("Z01","Z04"):(-0.50,0.25),
 ("Z01","Z05"):(-0.50,0.00),("Z02","Z03"):(0.25,1.38),("Z02","Z04"):(0.00,0.50),
 ("Z02","Z05"):(0.00,0.25),("Z03","Z04"):(-0.25,-0.88),("Z03","Z05"):(-0.25,-1.13),
 ("Z04","Z05"):(0.00,-0.25)}

def near(a,b,dp): return abs(round(a,dp)-b) <= 0.06   # rounding-boundary tolerant
P=[]; F=[]
def rec(ok,msg): (P if ok else F).append(msg)

derived={}
for z,(cc,cs,cb,cbo, rc,rs,rb,rbm) in EIGHT.items():
    Nc=cc+cs+cb+cbo; Nr=rc+rs+rb+rbm; n=Nc+Nr
    recc=100*(cc+cs)/Nc; recr=100*(rc+rs)/Nr
    fpr=100*(cb+cbo)/Nc; fnr=100*(rb+rbm)/Nr
    saves=cs+rs; jwrong=(cs+cbo)+(rs+rbm); brks=cb+rb; jcorr=(cc+cb)+(rc+rb)
    sr=100*saves/jwrong; brk=100*brks/jcorr
    derived[z]=dict(Nc=Nc,Nr=Nr,recc=recc,recr=recr)
    # A. conservation
    rec(n==ANALYSED[z], f"A {z}: 8-cell sums to n  ({n} vs {ANALYSED[z]})")
    rec(Nr==799, f"A {z}: ROGUE N = 799  (got {Nr})")
    # B. §5.2.1 two-table reconciliation (derive strat from 8-cell)
    cells=[("clean-corr",cc,cc+cb),("clean-wrong",cs,cs+cbo),
           ("rogue-corr",rc,rc+rb),("rogue-wrong",rs,rs+rbm)]
    for (lbl,dn,dN),(rn,rN) in zip(cells,STRAT[z]):
        rec((dn,dN)==(rn,rN), f"B {z} §5.2.1 {lbl}: 8-cell gives {dn}/{dN}, paper prints {rn}/{rN}")
    # C/D/E reported vs derived
    rc_,rr_,sr_,br_=REC[z]; fpr_,fnr_=FF[z]
    rec(near(recc,rc_,1), f"C {z} recovery CLEAN: derived {recc:.2f} -> paper {rc_}")
    rec(near(recr,rr_,1), f"C {z} recovery ROGUE: derived {recr:.2f} -> paper {rr_}")
    rec(near(fpr,fpr_,1), f"D {z} FPR: derived {fpr:.2f} -> paper {fpr_}")
    rec(near(fnr,fnr_,1), f"D {z} FNR: derived {fnr:.2f} -> paper {fnr_}")
    rec(near(sr,sr_,2),   f"E {z} save-rate: derived {sr:.2f} -> paper {sr_}")
    rec(near(brk,br_,2),  f"E {z} break-rate: derived {brk:.2f} -> paper {br_}")

# F. §5.3.1 deltas = differences in exact derived recovery
for (a,b),(dc,dr) in DELTA.items():
    cd=derived[a]["recc"]-derived[b]["recc"]; rd=derived[a]["recr"]-derived[b]["recr"]
    rec(near(cd,dc,2), f"F {a}-{b} CLEAN delta: derived {cd:+.2f}pp -> paper {dc:+.2f}")
    rec(near(rd,dr,2), f"F {a}-{b} ROGUE delta: derived {rd:+.2f}pp -> paper {dr:+.2f}")

# G. abstract headline ranges
allrec=[derived[z][k] for z in EIGHT for k in("recc","recr")]
allfpr=[FF[z][0] for z in EIGHT]; allfnr=[FF[z][1] for z in EIGHT]
rec(near(min(allrec),97.9,1) and near(max(allrec),99.5,1), f"G recovery range: {min(allrec):.1f}-{max(allrec):.1f}% -> paper 97.9-99.5%")
rec(max(allfpr)==1.0, f"G max FPR = {max(allfpr)}% -> paper 1.0%")
rec(max(allfnr)==2.1, f"G max FNR = {max(allfnr)}% -> paper 2.1%")

print(f"\n{'='*70}\nINTERNAL CONSISTENCY: {len(P)} passed, {len(F)} failed\n{'='*70}")
if F:
    print("\nFAILURES:")
    for m in F: print("  X", m)
else:
    print("\nAll cross-table ties hold. Representative checks:")
    for m in P[:6]+["..."]+P[-4:]: print("  -", m)
print(f"\nNote: §5.5 reliability stats (ICC 0.979, Krippendorff alpha 0.238, Gate-B kappa 0.515)")
print("are NOT derivable from these tables and remain unchecked here -- they need the")
print("stability run output to verify (todo 03/05).")
