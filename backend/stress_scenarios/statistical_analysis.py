"""Statistical analysis for stress test results"""
import numpy as np
from scipy import stats
from typing import Dict, List, Tuple, Any
from dataclasses import dataclass


@dataclass
class TierStatistics:
    """Statistical summary for a tier"""
    tier: int
    n: int
    mean: float
    std: float
    sem: float  # Standard error of mean
    ci_95_lower: float
    ci_95_upper: float
    min: float
    max: float
    median: float


def calculate_tier_statistics(scores: List[float], tier: int) -> TierStatistics:
    """Calculate comprehensive statistics for a tier"""
    n = len(scores)
    mean = np.mean(scores)
    std = np.std(scores, ddof=1)
    sem = stats.sem(scores)
    
    # 95% confidence interval
    ci = stats.t.interval(0.95, n-1, loc=mean, scale=sem)
    
    return TierStatistics(
        tier=tier,
        n=n,
        mean=round(mean, 2),
        std=round(std, 2),
        sem=round(sem, 2),
        ci_95_lower=round(ci[0], 2),
        ci_95_upper=round(ci[1], 2),
        min=round(min(scores), 2),
        max=round(max(scores), 2),
        median=round(np.median(scores), 2),
    )


def compare_tiers(
    tier1_scores: List[float],
    tier2_scores: List[float],
    tier1_name: str = "Tier 1",
    tier2_name: str = "Tier 2",
) -> Dict[str, Any]:
    """Perform t-test to compare two tiers"""
    
    # Independent samples t-test
    t_stat, p_value = stats.ttest_ind(tier1_scores, tier2_scores)
    
    # Effect size (Cohen's d)
    pooled_std = np.sqrt(
        (np.std(tier1_scores, ddof=1)**2 + np.std(tier2_scores, ddof=1)**2) / 2
    )
    cohens_d = (np.mean(tier1_scores) - np.mean(tier2_scores)) / pooled_std
    
    # Interpretation
    if p_value < 0.001:
        significance = "***"
        interpretation = "Highly significant"
    elif p_value < 0.01:
        significance = "**"
        interpretation = "Very significant"
    elif p_value < 0.05:
        significance = "*"
        interpretation = "Significant"
    else:
        significance = "ns"
        interpretation = "Not significant"
    
    return {
        "comparison": f"{tier1_name} vs {tier2_name}",
        "t_statistic": round(t_stat, 3),
        "p_value": round(p_value, 4),
        "significance": significance,
        "interpretation": interpretation,
        "cohens_d": round(cohens_d, 3),
        "effect_size": "Large" if abs(cohens_d) > 0.8 else "Medium" if abs(cohens_d) > 0.5 else "Small",
    }


def generate_statistical_report(
    tier1_scores: List[float],
    tier2_scores: List[float],
    tier3_scores: List[float],
) -> str:
    """Generate comprehensive statistical report"""
    
    # Calculate statistics for each tier
    stats1 = calculate_tier_statistics(tier1_scores, 1)
    stats2 = calculate_tier_statistics(tier2_scores, 2)
    stats3 = calculate_tier_statistics(tier3_scores, 3)
    
    # Pairwise comparisons
    comp_1v2 = compare_tiers(tier1_scores, tier2_scores, "Tier 1 (Solo LLM)", "Tier 2 (Math Geek)")
    comp_1v3 = compare_tiers(tier1_scores, tier3_scores, "Tier 1 (Solo LLM)", "Tier 3 (Probing)")
    comp_2v3 = compare_tiers(tier2_scores, tier3_scores, "Tier 2 (Math Geek)", "Tier 3 (Probing)")
    
    # Generate report
    report = f"""# Statistical Analysis Report

## Sample Size
- N = {stats1.n} per tier
- Total observations: {stats1.n * 3}

## Descriptive Statistics

| Tier | Mean | SD | SEM | 95% CI | Min | Max | Median |
|------|------|----|----|--------|-----|-----|--------|
| Tier 1 (Solo LLM) | {stats1.mean}% | {stats1.std} | {stats1.sem} | [{stats1.ci_95_lower}, {stats1.ci_95_upper}] | {stats1.min}% | {stats1.max}% | {stats1.median}% |
| Tier 2 (Math Geek) | {stats2.mean}% | {stats2.std} | {stats2.sem} | [{stats2.ci_95_lower}, {stats2.ci_95_upper}] | {stats2.min}% | {stats2.max}% | {stats2.median}% |
| Tier 3 (Probing) | {stats3.mean}% | {stats3.std} | {stats3.sem} | [{stats3.ci_95_lower}, {stats3.ci_95_upper}] | {stats3.min}% | {stats3.max}% | {stats3.median}% |

## Pairwise Comparisons (Independent t-tests)

### {comp_1v2['comparison']}
- t = {comp_1v2['t_statistic']}, p = {comp_1v2['p_value']} {comp_1v2['significance']}
- Cohen's d = {comp_1v2['cohens_d']} ({comp_1v2['effect_size']} effect)
- **{comp_1v2['interpretation']}**

### {comp_1v3['comparison']}
- t = {comp_1v3['t_statistic']}, p = {comp_1v3['p_value']} {comp_1v3['significance']}
- Cohen's d = {comp_1v3['cohens_d']} ({comp_1v3['effect_size']} effect)
- **{comp_1v3['interpretation']}**

### {comp_2v3['comparison']}
- t = {comp_2v3['t_statistic']}, p = {comp_2v3['p_value']} {comp_2v3['significance']}
- Cohen's d = {comp_2v3['cohens_d']} ({comp_2v3['effect_size']} effect)
- **{comp_2v3['interpretation']}**

## Interpretation

Significance levels: *** p<0.001, ** p<0.01, * p<0.05, ns = not significant
Effect sizes: |d| > 0.8 = Large, |d| > 0.5 = Medium, |d| ≤ 0.5 = Small
"""
    
    return report
