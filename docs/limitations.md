# Limitations (read before trusting any number)

1. **All operational data is synthetic.** `data/synthetic.py` generates the admissions history. It includes a scripted 2026 engineering-demand drop. No number on the site describes real SGI performance.
2. **Most sanctioned intakes are placeholders.** Only B.Ed (100), D.Pharm (60) and B.Pharm (100) come from a third-party directory. None comes from an approval letter.
3. **Intervention uplifts are priors, not evidence.** The 6–18% counselling uplift and the other ranges must be replaced with SGI's own A/B or geo-experiment results.
4. **Unit economics are placeholders.** Lifetime contribution per seat sets which options look worthwhile.
5. **Champion margin is thin.** At week 10, `bayes_blend` beats `seasonal_naive` by about 2% CRPS, which is effectively a tie. Pace models have a better Brier score for target-hit events. A per-target champion (distribution vs event) is a reasonable next step.
6. **Group intervals are tested on only 5 validation years.** The correlated draws fixed the most serious under-dispersion, but 5 group observations cannot establish calibration.
7. **No external drivers yet.** Counselling calendars, competitor fees, BSCC approval timing and entrance-exam dates are not modelled.
8. **Hospital entity unverified.** No healthcare engine will be built until it is verified.
9. **Admissions health is partial.** It covers the admissions domain only, not finance, academics, compliance or hospital.
10. **The decision loop is demonstrated, not proven.** Demo decisions remain PROPOSED. Decision-quality evaluation needs real decisions over several cycles.
