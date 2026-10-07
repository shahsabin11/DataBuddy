# DataBuddy v1 analytics spec

This document is the source of truth for the pilot workflow: clean a CSV or XLSX, explore it with charts, and, when the student wants one, run one group comparison, association test, or regression and report it. A chart is a complete run. A model is not required. The agent recommends and explains. The student decides. Anything outside the methods and chart types in this file is declined and logged, not attempted.

Pilot fields: biology, psychology, economics, anthropology, physics, chemistry, geosciences.
Typical table: 100 to 80,000 rows, fewer than 80 columns.
Stack assumed for computation: pandas, SciPy, statsmodels, matplotlib, inside the isolated sandbox. The language model never computes statistics.

## Standing rules

These rules outrank convenience. If a run would break one of them, the agent stops and asks.

1. One outcome per run. For a test, the student names the outcome, the predictors or grouping factor, and whether pairs are independent or matched. For a chart, the student names the variables and the chart type. The agent may suggest roles from the research question. It does not start a fit or a figure until the student confirms them.
2. The agent recommends a method or a chart type, names one or two alternatives, and states the trade-off in plain language. The sandbox runs only the option the student selects.
3. Default is a two-sided test at alpha = .05 with a 95% confidence interval. A one-sided test or a different alpha is allowed only if the student sets it before seeing the p-value.
4. No automated variable selection. The student lists at most 15 predictors. Stepwise search, all-subsets search, and "which variables matter?" fishing are out of scope.
5. No causal language. Results are associations unless the student, not the agent, supplies a design-based reason to use stronger wording. Even then the report states the design limitation.
6. Numbers in the report come from sandbox output. The model writes the explanation around those numbers and does not fill in a coefficient, p-value, or interval from memory.
7. The original upload is immutable. The working table is a replay of the cleaning log. Undo drops the last step and replays the prefix.
8. Every cleaning step, analysis, and decline is stored with the institution id, the user id, who decided (student or agent suggestion), the parameters, and the reason.
9. Do not silently downsample. If a table does not fit the sandbox limits, say so. A subsample runs only if the student sets the fraction and the random seed.
10. Ordinal versus interval is a student call. Likert-style codes are not treated as continuous, and not treated as nominal categories, until the student says which.

### Assumption heuristics

These are recommendation hints, not switches. Show the check. Recommend a row from the decision table. Wait.

| Check | How v1 does it | How the agent uses it |
| --- | --- | --- |
| Normality, n per group or residual n ≤ 50 | Shapiro-Wilk plus a normal Q-Q plot | A small p-value plus visible skew is a reason to recommend the nonparametric alternative. |
| Normality, 50 < n ≤ 5,000 | Q-Q plot, skewness, and kurtosis. Shapiro-Wilk may be shown and must be labeled as over-sensitive. | Do not recommend abandoning a mean comparison on Shapiro alone. |
| Normality, n > 5,000 | Q-Q plot and skewness only. Do not run Shapiro-Wilk. | Means are usually estimable. Recommend a rank test when skewness is severe (about \|skew\| > 2), outliers dominate the picture, or the student has classed the variable as ordinal. |
| Equal variance | Levene test with median center (Brown-Forsythe), plus a box plot | Unequal spread, especially with unequal n, recommends Welch rather than Student or classic ANOVA. |
| Linearity | Scatter with a straight fit for one predictor. Residual-versus-fitted for regression. | Curvature recommends a student-named transform or a rank correlation. The agent does not search transforms. |
| Heteroscedasticity | Breusch-Pagan on an OLS fit, read with the residual plot | If present, recommend the same OLS mean structure with HC3 standard errors. |
| Collinearity | VIF for models with two or more predictors | VIF ≥ 5 is a conversation. VIF ≥ 10 means those coefficients are unstable. The agent does not drop a predictor. |
| Influence | Cook's distance, flag points above 4/n | Flag only. A refit without those rows is a new, logged analysis the student must request. |
| Chi-square counts | Expected count for every cell | Any expected count below 5 changes the recommendation. See the decision table. |
| Logistic stability | Events per estimated parameter, and complete or quasi-complete separation | Under about 10 events per parameter: warn and still allow the run. Separation: do not report a finite odds ratio. |

## 1. Ranked methods

Rank is coverage across the pilot fields for a single-outcome course project, not statistical sophistication. Welch's ANOVA, Fisher’s exact test, Tukey HSD, Bonferroni pairwise follow-ups, and HC3 standard errors are in the product because the decision table offers them. They are alternatives, not extra research workflows.

| Rank | Method | When a student needs it | Assumptions | How v1 checks them | If assumptions fail, recommend |
| --- | --- | --- | --- | --- | --- |
| 1 | OLS linear regression, main effects, at most one pre-specified interaction | A continuous outcome and one or more numeric or categorical predictors. Calibration lines, covariate-adjusted associations, econ course regressions. | Independent errors, linearity in the parameters, no perfect collinearity. Homoscedasticity and normal errors matter most in small samples. | Residual plot, Q-Q of residuals, Breusch-Pagan, VIF, Cook's distance. | HC3 standard errors if the spread of residuals changes with the fit. A student-named log or square-root transform if they believe the scale is wrong. Rank correlation if there is a single numeric predictor and they only want association. |
| 2 | Pearson correlation | Two continuous variables, association rather than a covariate-adjusted model. | Linear relationship. The p-value leans on bivariate normality mainly in small samples. Sensitive to outliers. | Scatter, Q-Q of each variable, skewness. | Spearman. |
| 3 | Welch two-sample t-test | Two independent groups, continuous outcome. This is the usual two-group recommendation. | Independent observations. Sampling distribution of the mean difference is adequate (see normality heuristics). Does not assume equal variances. | Q-Q or Shapiro as above, Levene, box plot, group n. | Mann-Whitney if the outcome is ordinal or badly skewed. Student’s t only if variances and n are similar and the student wants the equal-variance test. |
| 4 | Chi-square test of independence | Two categorical variables. "Is group associated with category?" | Independent observations, mutually exclusive categories, expected cell counts generally ≥ 5. | Contingency table and expected counts. | Fisher’s exact test for a 2×2 with any expected count < 5. For a larger table, the student collapses categories, or they accept chi-square with the weak-count warning on the report. |
| 5 | One-way ANOVA | One continuous outcome, three or more independent groups, equal-variance mean comparison. | Independent observations, adequate normality per group, similar variances. | Per-group Q-Q, Levene, box plot. | Welch ANOVA if variances differ. Kruskal-Wallis if the outcome is ordinal or badly skewed. |
| 6 | Binary logistic regression | A binary outcome and one or more predictors the student listed. | Independent observations, linearity in the log-odds, no perfect collinearity, no complete separation, enough events for the number of parameters. | Events per parameter, separation check, VIF. | Chi-square or Fisher when there is a single categorical predictor and the question is association, not adjusted odds. Otherwise decline and point to consulting. |
| 7 | Spearman rank correlation | A monotonic association, an ordinal variable, skew, or outliers that would dominate Pearson. | Independent pairs. Measures monotone association, not specifically a straight line. | Scatter of the raw values and of the ranks. | Pearson, if the student cares about a straight line and outliers are not driving it. |
| 8 | Mann-Whitney U | Two independent groups. Ordinal outcome, or a continuous outcome where a mean is the wrong summary. | Independent observations. A shift in medians is a fair reading only if the two shapes are similar. Otherwise the result is about stochastic dominance: P(A > B). | Box plots and a density or histogram per group, looking for similar shape. | Welch t-test when n is large, skew is mild, and the student wants a difference in means. |
| 9 | Paired t-test | Two measurements on the same unit, or a matched pair, and the difference is the outcome. | Pairs independent of each other. Differences adequate for a mean. | Q-Q of the differences, histogram of the differences. | Wilcoxon signed-rank. |
| 10 | Kruskal-Wallis | Three or more independent groups, ordinal outcome or a mean comparison the student does not trust. | Independent observations. A median reading needs similar shapes. | Box plots per group. | Welch ANOVA when n is large and the student wants means. Classic ANOVA if normality and equal variance look acceptable. |
| 11 | Student’s two-sample t-test | Two independent groups, continuous outcome, similar variances, similar n. Kept because courses require it and it is appropriate in that case. | Everything Welch assumes, plus equal population variances. | Same as Welch, with Levene as the fork. | Welch if variances differ. Mann-Whitney if a mean is inappropriate. |
| 12 | Wilcoxon signed-rank | Paired measurements when the differences are skewed, ordinal, or heavy-tailed. | Pairs independent of each other. A "median difference" reading needs a roughly symmetric difference distribution. | Histogram and Q-Q of the differences. | Paired t-test when the differences support a mean and n is not tiny. |

### Effect sizes the report must include

| Method | Report | Notes |
| --- | --- | --- |
| Student or Welch t | Mean difference, 95% CI, both means and SDs, Hedges’ g | g uses the pooled SD and is labeled descriptive. The Welch CI is the inferential summary when variances differ. |
| Paired t | Mean of differences, 95% CI, paired d_z = mean difference / SD of differences | Label d_z so it is not read as a two-sample Cohen’s d. |
| Mann-Whitney | Medians and IQRs, rank-biserial correlation | State whether shapes looked similar enough for a median reading. |
| Wilcoxon signed-rank | Median of differences, matched rank-biserial correlation | Same symmetry caveat. |
| ANOVA | Group means and SDs, partial eta-squared | For one-way ANOVA, partial eta-squared equals eta-squared. |
| Welch ANOVA | Group means, Welch F or equivalent, partial eta-squared labeled descriptive | Pairwise follow-up is separate and opt-in. |
| Kruskal-Wallis | Medians and IQRs, epsilon-squared = H(n+1)/(n²−1) | Cite the formula on the report. |
| Chi-square | Cramer's V; phi when the table is 2×2 | Also show observed counts, expected counts, and standardized residuals. |
| Fisher’s exact | Odds ratio and CI, plus the table | 2×2 only. |
| Pearson | r, 95% CI via Fisher’s z, r² | |
| Spearman | rho and its p-value | Do not call rho a Pearson r. |
| OLS | B, SE, t, p, 95% CI for each term; R²; adjusted R²; residual DF; N | HC3 SE and CI when that option was selected. |
| Logistic | Log-odds and odds ratio, SE, z, p, 95% CI; N; number of events | Pseudo-R² may be shown only with the sentence that it is not variance explained. |

### APA sentences

Write these from sandbox fields. Use APA 7 form: no leading zero on statistics that cannot exceed 1 (`p = .034`), and `p < .001` rather than a rounded zero.

- Independent t: `t(df) = 2.45, p = .016, g = 0.63, 95% CI [0.12, 0.88]`
- Paired t: `t(df) = 2.45, p = .016, d_z = 0.40, 95% CI [0.08, 0.55]`
- ANOVA: `F(2, 57) = 4.12, p = .021, ηp² = .13`
- Chi-square: `χ²(1, N = 120) = 5.44, p = .020, φ = .21`
- Pearson: `r(98) = .34, 95% CI [.15, .50], p = .001`
- OLS term: `B = 1.20, SE = 0.31, t(96) = 3.87, p < .001, 95% CI [0.59, 1.81]`
- Logistic term: `OR = 1.85, 95% CI [1.10, 3.12], p = .021`

Welch degrees of freedom may be fractional. Report them to two decimals.

### Follow-ups the student must opt into

A significant omnibus test does not start pairwise tests by itself.

| After the student selected | If they then ask for pairwise comparisons | Alternative | Trade-off |
| --- | --- | --- | --- |
| One-way ANOVA | Tukey HSD | Bonferroni-adjusted pairwise Student t-tests | Tukey is built for all pairwise mean comparisons after ANOVA. Bonferroni is cruder and usually wider, and it is easier to explain. |
| Welch ANOVA | Bonferroni-adjusted pairwise Welch t-tests | Stop at the omnibus test | v1 does not run Games-Howell. Bonferroni on Welch tests matches the unequal-variance choice. It is conservative. |
| Kruskal-Wallis | Bonferroni-adjusted pairwise Mann-Whitney tests | Stop at the omnibus test | v1 does not run Dunn’s test, which avoids a dependency and a second ranking procedure. Bonferroni on Mann-Whitney is conservative and does not use the Kruskal-Wallis ranks. |
| Chi-square, table larger than 2×2 | Standardized residuals, already in the default table | Student-named collapsed table, as a new logged analysis | Residuals show which cells depart from independence. Collapsing changes the question. |

## 2. Decision table

Read top to bottom within a branch. The first row whose condition matches is the recommendation. Present that row and stop. The student picks the recommended method or an alternative on the row.

Branch 0 runs before any test. If branch 0 says stop, do not force the question into a later row.

| ID | Outcome | Predictor or design | Groups | Assumption result | Recommend | Alternative | Trade-off in plain language |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0.1 | Not yet confirmed | Roles not confirmed | Any | Student has not named the outcome, the predictors, the types, paired versus independent, and alpha | Ask for those items. Do not fit. | — | Guessing the research design would be a silent judgment call. |
| 0.2 | Several outcomes in the question | Any | Any | More than one outcome is named | Ask which single outcome this run uses | A later separate run for another outcome | Each extra outcome is another family of tests. Looping them silently spends the token budget and hides multiplicity. |
| 0.3 | More than 15 predictors | Any | Any | Student listed more than 15 predictors | Ask them to narrow the list. Do not drop terms for them. | Advisor or campus consulting | Choosing which variables to drop is the analysis. v1 has no honest automatic way to do it. |
| 0.4 | Identifier or unique-per-row column | High-cardinality id | Any | Predictor is unique per row, or the student labeled it an id | Exclude it and say why | Student overrides with a written reason | An id can produce a perfect, meaningless fit. |
| 0.5 | Counts, time, survival, clusters, many classes | Design needs a method in the out-of-scope list | Any | Question needs mixed models, time series, survival, Poisson, multinomial or ordinal regression, or a multi-way ANOVA | Decline with the out-of-scope message and log it | Reframe only if a row below truly matches, and only with the student agreeing to the narrower question | A simpler test that answers a different question is not a favor. |
| 0.6 | Continuous or ordinal | Two measurements on the same unit | 2 | Pairing is confirmed | Go to branch 2 | Branch 1 only if the student says the rows are independent | Treating paired data as two independent groups uses the wrong variance. |
| 1.1 | Continuous | One categorical factor, independent rows | 2 | Spread similar across groups, and normality heuristics are acceptable | Welch t-test | Student’s t-test; Mann-Whitney | Welch stays valid if the equal-variance reading is wrong. Student’s t is the textbook equal-variance test and is a bit more precise when that assumption holds. Mann-Whitney answers a rank question instead of a mean question. |
| 1.2 | Continuous | One categorical factor, independent rows | 2 | Normality heuristics acceptable, variances unequal | Welch t-test | Mann-Whitney | With unequal spread, Student’s t can give a badly calibrated p-value, especially when group sizes differ. Mann-Whitney avoids means but will not estimate a mean difference. |
| 1.3 | Continuous | One categorical factor, independent rows | 2 | Severe skew, heavy tails, or outliers dominate | Mann-Whitney | Welch t-test | The rank test is less driven by extreme values. The Welch test still estimates a mean, which can be the quantity the student cares about when n is large. |
| 1.4 | Ordinal | One categorical factor, independent rows | 2 | Student classed the outcome as ordinal | Mann-Whitney | Welch t-test only if the student reclasses the outcome as interval | Means of rank codes look precise and are hard to defend. Reclassing to interval is a measurement decision the student has to own. |
| 2.1 | Continuous difference | Paired or matched | 2 | Differences support a mean | Paired t-test | Wilcoxon signed-rank | The paired t-test estimates a mean change. Wilcoxon is less sensitive to a skewed difference and does not estimate that mean. |
| 2.2 | Continuous difference | Paired or matched | 2 | Differences are badly skewed or heavy-tailed | Wilcoxon signed-rank | Paired t-test | Same trade-off as 2.1, with the recommendation reversed. |
| 2.3 | Ordinal | Paired or matched | 2 | Student classed the outcome as ordinal | Wilcoxon signed-rank | Paired t-test only if the student reclasses the outcome as interval | Same measurement point as row 1.4. |
| 3.1 | Continuous | One categorical factor, independent rows | 3 or more | Normality heuristics acceptable, variances similar | One-way ANOVA | Kruskal-Wallis; Welch ANOVA | ANOVA compares means and is the course default when spread is similar. Kruskal-Wallis compares ranks. Welch ANOVA protects the p-value if the equal-variance reading is optimistic. |
| 3.2 | Continuous | One categorical factor, independent rows | 3 or more | Normality heuristics acceptable, variances unequal | Welch ANOVA | Kruskal-Wallis | Classic ANOVA’s p-value is the one at risk here. Welch keeps the mean comparison. Kruskal-Wallis changes the question to ranks. |
| 3.3 | Continuous | One categorical factor, independent rows | 3 or more | Severe skew or dominating outliers | Kruskal-Wallis | Welch ANOVA | Ranks limit the pull of extreme scores. Welch still targets means, which can be right at large n. |
| 3.4 | Ordinal | One categorical factor, independent rows | 3 or more | Student classed the outcome as ordinal | Kruskal-Wallis | Welch ANOVA only if the student reclasses the outcome as interval | Same measurement point as row 1.4. |
| 4.1 | None named; both variables continuous | Association, not a covariate model | — | Cloud looks roughly linear and outliers are not in control | Pearson correlation | Spearman; OLS if they need a slope and an intercept | Pearson matches a straight-line association and is what most courses report. Spearman keeps a curved but steadily increasing pattern from being called "no relationship." OLS is the right step up only if they want the line itself. |
| 4.2 | None named; both continuous, or either is ordinal | Association | — | Monotone pattern, clear curve, ordinal scale, or outliers dominate | Spearman correlation | Pearson | Spearman answers "does one tend to rise with the other?" Pearson answers "how linear is it?" and will shrink toward zero under a curve or a few extreme points. |
| 5.1 | Continuous | One or more predictors the student listed | — | Residual plot is roughly formless, spread is stable, VIF is low | OLS | Pearson or Spearman when there is one numeric predictor and no covariates | OLS estimates each coefficient while holding the other listed predictors fixed. A correlation ignores covariates. That is simpler and it answers a smaller question. |
| 5.2 | Continuous | One or more predictors | — | Residual spread changes with the fitted values | OLS with HC3 standard errors | Student-named log or square-root transform, then OLS, as a new logged run | HC3 keeps the mean model and widens the uncertain coefficients. A transform changes the scale of the outcome, which changes the sentence the student can write. |
| 5.3 | Continuous | Two or more predictors | — | VIF ≥ 5 for one or more terms | Stop and show the VIF table. Ask the student which collinear term to remove or combine. | Fit anyway, with the instability written on the report | Dropping a collinear variable changes the question. Fitting anyway produces coefficients that jump when a row changes. |
| 5.4 | Continuous | Predictors include categories | — | Types confirmed | OLS with dummy codes. Student picks the reference level. Agent may suggest the modal level or a control group. | A group-comparison row, if there is exactly one categorical predictor and no covariates | Dummy codes make the coefficients "difference from the reference." Picking the reference changes the story, not the fit. A plain ANOVA is easier to read when there are no covariates. |
| 5.5 | Continuous | Student asks for one named interaction | — | They name the two variables before the run | OLS with main effects plus that one interaction | Main effects only | An interaction asks whether one association changes across levels of the other. Adding it because the fit improves is a second, unplanned test. v1 allows one interaction that was named in advance. |
| 6.1 | Binary | One categorical predictor, no covariates | 2 or more levels | The question is "are these associated?" and expected counts are ≥ 5 | Chi-square | Logistic regression; Fisher if the table is 2×2 | Chi-square is the direct test of association. Logistic estimates an odds ratio and is the path if they expect to add covariates later. |
| 6.2 | Binary | One categorical predictor | 2×2 table | Any expected count < 5 | Fisher’s exact test | Chi-square with the weak-count warning | Fisher stays calibrated in a sparse 2×2. Chi-square is approximate and can be off when cells are thin. |
| 6.3 | Binary | One categorical predictor | Larger than 2×2 | Any expected count < 5 | Ask the student to collapse categories, then return to 6.1 as a new logged analysis | Chi-square with the warning left on the report | Collapsing raises expected counts and changes the categories the conclusion is about. v1 does not run exact tests on large tables. |
| 6.4 | Binary | One or more predictors | — | Events per parameter are adequate and there is no separation | Logistic regression | Chi-square, if there is a single categorical predictor | Logistic estimates adjusted odds. Chi-square does not adjust and does not take numeric predictors. |
| 6.5 | Binary | Any | — | Complete or quasi-complete separation | Do not report odds ratios. Explain which predictor or cell separates the outcome. | Student drops or recodes that predictor in a new logged run, or goes to consulting | A separated logistic coefficient runs off to infinity. Printing a huge odds ratio looks like a result and is not one. Firth logistic is out of scope. |
| 6.6 | Binary | Any | — | Fewer than about 10 outcome events per parameter | Warn, then fit only if the student confirms | Consulting | The odds ratios can look precise while being unstable. Blocking every small sample would make the pilot useless; hiding the warning would be worse. |
| 7.1 | Categorical, more than two levels | One categorical predictor | Any | Expected counts ≥ 5, association question | Chi-square | Collapsed 2×2 only if the student defines the collapse first | v1 has no multinomial model. Chi-square answers association and does not produce adjusted effects. |
| 7.2 | Categorical, more than two levels | Numeric or several predictors | Any | They want a regression | Decline. Out of scope. | Chi-square only if they reduce the design to two categorical variables | Multinomial and ordinal regression are real judgment calls and a second modeling stack. |

## 3. Cleaning

The original file stays as uploaded. Each operation appends a log row: operation, parameters, actor (`agent_auto` or `student`), reason, row count before and after, column names before and after, timestamp, user id, institution id. Undo replays the log without the last row. A destructive step is never bundled into an automatic pass.

| Operation | What it does | Who acts | Why this split |
| --- | --- | --- | --- |
| Profile | Types, missing counts, unique counts, duplicate-row count, constant columns, likely ids. Read only. | Automate | It does not change the table. |
| Trim surrounding whitespace on text | `" yes "` becomes `"yes"`. | Automate and log | Lossless for analysis and reversible by replay from the original. |
| Drop fully empty rows and fully empty columns | Removes rows and columns with no values at all. | Automate and log | There is no observation or variable to analyze. The log still records the drop. |
| Lossless numeric coercion | A text column whose every non-missing value parses as a number, with no leading zeros lost, and the student has not marked it as a code or id. | Automate, log, and show a before/after sample | Nothing numeric changes. Stop and ask if any value fails, leading zeros would disappear, or the name looks like an id or code. |
| Proposed types | Show inferred type and the evidence. Integers with few distinct values are marked ambiguous. | Student confirms | A 1–5 code may be a category, an ordinal score, or a count. That choice selects the branch of the decision table. |
| Sentinel missing values | Detect tokens such as `NA`, `N/A`, `null`, `missing`, `.`, and suspicious numeric codes such as `999` or `-99`. | Student confirms the list before they become missing | `999` is sometimes a real measurement. Converting it changes every later result. |
| Blank text to missing | Empty strings become missing. | Student confirms | It changes the missingness count and therefore listwise N. |
| Duplicate rows | Report the count and a sample of duplicated keys. | Detection is automatic. Deletion requires the student. | In a long table, duplicate rows are often double entry. In a short table they may be real repeated observations. |
| Drop a column that contains data | Removes a variable from the working table. | Student confirms | Dropping a column the model dislikes would be variable selection. |
| Row filter | Keeps a subset the student defines, such as one campus or age ≥ 18. | Student confirms | This defines the population. It is not a cleaning detail. |
| Listwise deletion | Drops rows missing the outcome or a chosen predictor. | Student confirms | It changes N and can bias the result when missingness is not pure accident. Report N before and after. |
| Simple imputation | Median for a numeric column, or mode for a categorical column, and only for columns the student names. | Student confirms | Imputed values pull results toward the center and shrink standard errors if treated as real. Mark imputed cells in the log. Mean imputation and multiple imputation are out of scope. |
| Outliers | Report IQR fences (1.5 and 3) and \|z\| > 3. Do not remove them in the profile. | Student confirms any deletion or winsorizing, and names the columns and the fence | Outlier rules change the estimated effect. The profile’s job is to show candidates. |
| Recode or collapse categories | Applies a mapping the student writes. | Student confirms | Combining "strongly agree" with "agree" changes both chi-square and regression. |
| Derived column | Builds a column from a formula the student writes, including a named log or square-root transform. | Student confirms | The agent does not hunt for a transform that improves p. |
| Binning a numeric variable | Cuts a number into categories with student-named edges. | Student confirms | Binning throws away information and is easy to tune toward a desired result. |
| Reference level | Chooses the dummy baseline. | Student confirms | The agent may suggest the control group or the modal category. |

v1 imputation is a single median or mode, fit on the working table after the student confirms, with imputed cells flagged. It is a teaching baseline, not a missing-data analysis. If missingness is substantial, the report says the result assumes the filled-in values and points the student to their advisor for a real missing-data design.

## 4. Visualizations

Chart creation is its own feature. A student can ask for a figure during exploration and never run a test. The agent recommends a chart from the table below, names an alternative, and waits. `render_chart` then draws that named chart with code you wrote. The figure is stored with the project, the institution, and the cleaning-log version it used. It does not change the working table.

A fitted line, a residual plot, or a coefficient plot is drawn only when the student has also selected the matching test. A scatter by itself does not imply a correlation test.

| Variables the student confirmed | Recommend | Alternative | Trade-off in plain language |
| --- | --- | --- | --- |
| One continuous variable | Histogram | Box plot | A histogram shows the shape. A box plot is plainer about the median and the extreme values. |
| One continuous variable and one grouping variable | Box plot by group | Histogram for each group | A box plot is the easier comparison across groups. Separate histograms show the shape inside each group. |
| Two continuous variables | Scatter plot | A histogram of each variable | A scatter shows how the two move together. Separate histograms only describe each one. |
| One categorical variable | Bar chart of counts | Count table | The bar chart is the picture. The table is the exact count. |
| Two categorical variables | Heatmap of the count table | Grouped bar chart | The heatmap shows where the counts sit. The grouped bar chart is easier to compare one category at a time. |

If the student wants a layout this table does not name, `custom_plot` may change titles, labels, colors, or the arrangement of the same variables. The student approves that source before it runs. The image still cannot be treated as a test result.

These chart types are out of scope, and the agent declines them instead of stretching `custom_plot`: interactive dashboards, maps, network diagrams, 3D charts, and animation. v1 uses matplotlib only. A second plotting library is a new dependency and is not in the budget.

Diagnostic figures that belong to a test the student already chose:

| Plot | When it is produced |
| --- | --- |
| Histogram | With a group comparison, so the student can see shape. Facet or overlay by group. |
| Box plot | With a t-test, ANOVA, Welch ANOVA, Mann-Whitney, or Kruskal-Wallis. |
| Bar chart of counts | With a chi-square or Fisher run, beside the count table. |
| Scatter with fitted line | With Pearson, Spearman, or simple OLS. The line on a Spearman scatter is labeled as a visual aid. OLS includes the 95% mean band. |
| Residual versus fitted | With every OLS model. |
| Normal Q-Q | With parametric group tests, and on the residuals of every OLS model. |
| Coefficient plot | Optional picture of the OLS or logistic estimates and intervals already in the table. It does not add a method. |

## 5. Other outputs

Every plot and table is saved with the analysis id, institution id, and the cleaning-log version it used. Axes use confirmed variable names and units when the student supplied them. A plot title states the variables and the chart type, or the method and the comparison. It does not state a finding.

### Tables

| Table | Contents |
| --- | --- |
| Variable confirmation | Name, inferred type, confirmed type, role, missing percent, distinct values. |
| Descriptives, continuous | N, missing, mean, SD, median, IQR, min, max. Overall and by group when relevant. |
| Descriptives, categorical | Counts and percentages, including missing as its own row until the student decides. |
| Assumption checks | The checks from the heuristics table that apply to this run, with the statistic, the p-value where one exists, and the plain-language reading. |
| Primary result | APA sentence plus a one-row machine-readable result: test, statistic, df, p, effect size, CI, N. |
| Group or coefficient detail | ANOVA or pairwise table, or regression terms with B or OR, SE, statistic, p, and CI. |
| Contingency detail | Observed, expected, and standardized residual for each cell. |
| Cleaning log | Every operation already applied to the version under analysis. |
| Decision record | For a test: recommended method, alternatives, the method the student selected, alpha, one-sided or two-sided, and the assumption row id. For a chart: recommended chart, alternative, the chart the student selected, and the variables. |

## 6. Out of scope

If a request matches this list, the agent does not improvise a nearby model or chart. It sends the message below, logs `out_of_scope` with the institution id and the phrase the student used, and waits for a question that matches the decision table or the chart table.

- Mixed-effects and hierarchical models, random intercepts, clustered or nested standard errors
- Repeated-measures ANOVA, MANOVA, and factorial ANOVA beyond one factor
- ANCOVA as its own procedure. The allowed reframe is OLS with the covariates the student names.
- Mediation, and any search for interactions. One interaction the student names before fitting is in scope.
- Poisson, negative binomial, and other generalized linear models besides binary logistic regression
- Multinomial logistic regression and ordinal logistic regression
- Time series, forecasting, panel models, and date-based lags
- Survival and reliability models
- Principal components, factor analysis, structural equation models
- Machine learning: trees, forests, boosting, support vector machines, clustering, neural nets
- Regularized regression and any automatic variable selection
- Bayesian models
- Causal estimators: instrumental variables, difference-in-differences, regression discontinuity, matching, weighting
- Survey weights and complex samples
- Spatial statistics
- Multiple imputation and other missing-data models
- Power analysis, including post-hoc power
- Nonlinear curve fitting beyond a student-named log or square-root transform inside OLS
- Equivalence tests, two one-sided tests
- Meta-analysis
- Text, images, and audio as input data
- Interactive dashboards, maps, network diagrams, 3D charts, and animated charts
- Firth logistic regression, Dunn’s test, and Games-Howell post-hoc tests
- Exact tests on tables larger than 2×2

Message to show, with the method name filled in:

> DataBuddy v1 cleans a table, makes histograms, box plots, bar charts, and scatter plots, and runs group comparisons, correlations, chi-square tests, and linear or binary logistic regression. **{method}** is outside that set, so I will not run it or approximate it. This needs a statistician who knows your design. Please take it to your advisor or your campus statistical consulting service. I have logged the request on your project so the record shows what you asked for and that it was not attempted.

## Budget and boundary notes

- No new paid service is required. Prefer templated decision-row explanations filled with sandbox numbers over asking the model to restate a textbook on every run.
- Do not add Python packages for Dunn, Games-Howell, multiple imputation, penalized logistic, or a second plotting library in v1. Charts use matplotlib.
- Computation stays in the sandbox: no network, resource limits, and no other student’s files. The model sees sandbox results, not a second copy of someone else’s data.
- Logs, outputs, and declines carry `institution_id` from the first schema. The pilot campus is a row in `institutions`, not a hardcoded email domain.
- Token metering follows the existing per-student and per-institution budget. A declined out-of-scope request should log a short completion, not a long attempted analysis.

## What this spec is for

Use it as the system prompt’s method contract and as the checklist for sandbox functions, including `render_chart`. If a course project needs a method or a chart type on the out-of-scope list, the honest pilot behavior is to log the gap. That gap is a finding for the capstone write-up, not a reason to widen v1 during the 10-week pilot.
