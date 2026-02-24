# Statistical Analysis Report

## Sample Size
- N = 30 per tier
- Total observations: 90

## Descriptive Statistics

| Tier | Mean | SD | SEM | 95% CI | Min | Max | Median |
|------|------|----|----|--------|-----|-----|--------|
| Tier 1 (Solo LLM) | 76.33% | 3.65 | 0.67 | [74.97, 77.7] | 57.0% | 77.0% | 77.0% |
| Tier 2 (Math Geek) | 92.69% | 0.12 | 0.02 | [92.65, 92.74] | 92.67% | 93.33% | 92.67% |
| Tier 3 (Probing) | 79.46% | 0.0 | 0.0 | [79.46, 79.46] | 79.46% | 79.46% | 79.46% |

## Pairwise Comparisons (Independent t-tests)

### Tier 1 (Solo LLM) vs Tier 2 (Math Geek)
- t = -24.525, p = 0.0 ***
- Cohen's d = -6.332 (Large effect)
- **Highly significant**

### Tier 1 (Solo LLM) vs Tier 3 (Probing)
- t = -4.69, p = 0.0 ***
- Cohen's d = -1.211 (Large effect)
- **Highly significant**

### Tier 2 (Math Geek) vs Tier 3 (Probing)
- t = 601.455, p = 0.0 ***
- Cohen's d = 155.295 (Large effect)
- **Highly significant**

## Interpretation

Significance levels: *** p<0.001, ** p<0.01, * p<0.05, ns = not significant
Effect sizes: |d| > 0.8 = Large, |d| > 0.5 = Medium, |d| ≤ 0.5 = Small
