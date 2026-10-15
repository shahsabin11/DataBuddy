# DataBuddy v1 collaboration model

The agent recommends and explains. The student decides. This note is the
product version of that rule. Implementation details for sandbox gates are in
[`threat-model.md`](threat-model.md). Methods and charts are in
[`analytics-spec.md`](analytics-spec.md).

## Roles in a session

| Actor | Does | Does not |
| --- | --- | --- |
| Student | Names the research question, confirms variable types and roles, chooses chart type and test, approves destructive cleans and free-form code, interprets results | Have to write every line of analysis code |
| Agent | Profiles the file, suggests cleans and chart/test options with trade-offs, runs only the approved tool, formats tables and plots from sandbox output | Silently pick a test, drop predictors, change alpha after seeing *p*, claim causality, invent numbers |
| Sandbox | Executes fixed tools (and approved free-form pandas/matplotlib) in isolation | Talk to the network, hold secrets, keep files between runs |

## When the student must approve

Before the sandbox runs:

1. **Chart type** — agent recommends from the chart table; student confirms variables and type (`render_chart`).
2. **Analysis method** — agent recommends from the decision table; student picks the method (or an alternative) before `run_comparison` / `run_regression`.
3. **Destructive cleaning** — listwise delete, impute, drop outliers, recode, filter rows, drop columns with data, binning, sentinel→missing, duplicate drop.
4. **Free-form code** — full source for `transform_frame` or `custom_plot`. A transform that changes values needs a second accept after the before/after diff.
5. **Alpha / one-sided tests / subsample / dropping influential rows** — set in the open before the new *p*-value exists.

Automatic and reversible (logged; student can undo):

- Profile
- Trim whitespace
- Drop fully empty rows/columns
- Lossless numeric coercion (with sample shown)

## Decision record

Every step stores:

- what was done
- why (agent rationale or student note)
- alternatives shown
- who decided (`student` or `agent_auto` for the safe cleans)
- institution id and user id

The report panel binds numbers and images to sandbox output. The model only narrates those fields.

## Out of scope requests

If the student asks for a method or chart outside the analytics spec, the agent
declines, shows the consulting message, logs `out_of_scope`, and does not start
a sandbox. That refusal is collaboration too: the honest answer beats a silent
approximation.

## Pause behavior

While the student decides, the model turn ends and no sandbox is left running.
The next message resumes from a LangGraph checkpoint for that project.
