# DataBuddy v1 sandbox threat model

This note closes the open decision: how much autonomy the code-execution sandbox gets, and how student data is isolated per run. It sits on the stack in `docs/architecture.md` and the method contract in `docs/analytics-spec.md`.

`docs/collaboration-model.md` is not in the repo. The approval rules in section 6 are the sandbox half of that contract, taken from the analytics spec: the agent recommends, the student decides, and every step records who decided.

Host remains the one already chosen: a hosted sandbox (E2B or Modal), never the FastAPI process. Architecture recommends E2B Hobby. Either host can carry this policy. The gaps in section 8 are yours on both.

## Decision

Use a tight hybrid.

- Statistics, assumption checks, and the charts the spec names are fixed Python functions you wrote and tested. The model passes parameters. It does not write that code. `render_chart` can run with no test attached.
- Cleaning and extra plots may be free-form Python, limited to an allow-list of pandas, numpy, and matplotlib. That code cannot import SciPy, statsmodels, or scikit-learn, and its stdout is never parsed as a test result.
- The security boundary is a fresh sandbox with no network, no secrets, and only this project’s files. The allow-list is a scope and integrity control. It is not the isolation mechanism.

A loose hybrid, where one Python process may import the statistics libraries, is the wrong reading of option (b). A fixed-only toolset is the fallback if the free-form runner slips past the term.

## Capstone defense

Each tool run starts a new sandbox with no outbound network, no credentials, and only that project’s dataset versions mounted, so generated code cannot reach another student’s files or the database. Official statistics come from fixed functions the student selected. Free-form Python is limited to pandas and matplotlib for cleaning and plots, and a script that changes rows becomes the working dataset only after the student sees the diff and approves it. The sandbox is destroyed at the end of the run, which keeps the pilot inside the hosting budget and leaves a log of the code, the limits, and who approved the step.

## 1. Autonomy

| | (a) Fixed tools only | (b) Tight hybrid, recommended | (c) Free-form Python |
| --- | --- | --- | --- |
| What the model may run | Parameterized calls such as `run_welch` and `fit_ols` | Those same functions, plus `transform_frame` and `custom_plot` under the allow-list | Any Python the sandbox image can import |
| Security risk | Lowest. The model picks arguments, not programs. A hostile cell can still trick the model into a bad argument. | Contained if, and only if, free-form code cannot emit an official p-value. The sandbox still has to stop network, secrets, and cross-tenant files. An import checker will miss some Python tricks. | The sandbox still stops network and cross-tenant reads. The model can attempt every library in the image, including clients and serialization, and you review a new program on every run. |
| Statistical reliability | Highest. Results come from code you tested. Out-of-scope methods have no function to call. | High for tests, because those stay on the fixed path. Cleaning quality depends on the student reading the diff. A plot can still mislead. It cannot become the regression table. | Lowest. The model can drop rows inside a “plot” script, change a test after the student chose one, or run a method the spec declines. The report will look official. |
| Flexibility for students | The cleaning operations and plots in the analytics spec. A new spreadsheet layout waits on you. | Spec operations, plus a readable pandas script for a one-off reshape, and a matplotlib figure when the named plots are not the figure they need. | Any analysis a notebook could do, including the ones v1 is supposed to decline. |
| Build effort in one term | The spec’s functions, plots, and cleaning operations. You write these under every option, because they are the product. | Those functions, plus one restricted runner, a code-approval screen, and a before/after diff. Fits the term if there are two free-form tools, not a notebook. | A single execute endpoint looks small and is the largest product: reversibility, spec enforcement, and a review UI for arbitrary programs. |

### Why the tight hybrid, and not the other two

Option (c) treats the sandbox as a complete safety case. The sandbox answers confidentiality of other tenants. It does not answer whether the number on the report is the test the student chose. That second failure is the one a research app has to defend.

Option (a) is the cleanest story and the smallest security surface. It is the wrong default for this pilot because files from seven fields will include layouts your fixed cleaners will not name in advance. Every one of those becomes a patch you ship during the ten weeks. The analytics spec already calls cleaning mechanical and logged. A short pandas script the student can read is the mechanical escape hatch.

Option (b) is right when the two paths cannot share an interpreter policy. FastAPI, not the model, chooses the entrypoint.

| Tool | Who writes the code | Imports it may use | What it may change |
| --- | --- | --- | --- |
| `profile_table`, assumption checks | You | pandas, numpy, matplotlib | Nothing. Read-only. |
| `apply_confirmed_clean` for the operations the spec marks automatic or student-confirmed | You | pandas, numpy | The working table, with the logged operation. |
| `render_chart` | You | pandas, numpy, matplotlib | Nothing in the dataset. Writes the one image the student confirmed: histogram, box plot, bar chart, grouped bar, heatmap, or scatter. |
| `run_comparison`, `run_regression` | You | pandas, numpy, SciPy, statsmodels | Nothing in the dataset. Writes `result.json` only. |
| Diagnostic plots for a test the student already selected | You | pandas, numpy, matplotlib | Nothing in the dataset. Writes image files. |
| `transform_frame` | The model, after the student approves the source | pandas, numpy, and the stdlib modules `math`, `re`, `datetime`, `collections`, `itertools` | A candidate table in `/output`. It becomes the working version only after the diff is accepted. |
| `custom_plot` | The model, after the student approves the source | Those modules plus matplotlib | Image files only. |

SciPy, statsmodels, and scikit-learn stay in the image so your fixed functions can import them. The free-form runner installs an import hook that refuses them. Official numbers are read from `result.json` produced by the fixed entrypoint. Free-form stdout is stored, capped, and never turned into an APA sentence.

The allow-list is enforced twice: an AST check before the run, and the import hook inside the run. Both are best-effort against a determined payload. A student who can already run code in the sandbox is inside an isolated microVM with only their own file. The checker exists so a routine prompt, or a cell that says “import statsmodels,” does not become a silent test.

Column names and cell values are data. Fixed tools receive column names as validated parameters drawn from the header, not as fragments interpolated into source. The free-form source that runs is the string the student approved, written into the sandbox by FastAPI. The running code does not get to swap that file for a different program and have you treat the swap as the approved script.

## 2. Isolation per run

One fresh sandbox per tool execution, destroyed before the next model turn. That is stricter than one sandbox for a whole chat, and it is the policy.

A sandbox kept open for the chat would hold memory while the student reads a recommendation, would keep files created by the previous tool, and would hit the E2B Hobby one-hour cap during ordinary pauses. The architecture note already destroys the sandbox at the end of the tool call. This note confirms that.

What “the session’s data” means:

- FastAPI resolves `institution_id` and `project_id` from the server session, then copies in only the dataset versions that tool needs. Usually that is the current working table. A comparison against the original upload may include the original as a second read-only file.
- Those files are mounted under `/input` and made read-only before the tool process starts.
- The process writes only under `/output`.
- FastAPI collects `/output` and then destroys the sandbox.
- Nothing is paused, snapshotted, or mounted from a volume. The next tool, the next user, and the next institution get a new sandbox and a new copy.

The original upload in object storage is still immutable. A cleaning run does not overwrite it. An accepted diff is a new object key, logged in Postgres with the institution, the user, the approved source or the fixed operation name, and the row counts.

## 3. Network and file transfer

The sandbox has no outbound network, including DNS. Both products ship with outbound access on unless you turn it off. The create call sets the block every time. A later call that “clears network rules” is a bug, not a feature: E2B’s `update_network` with an empty configuration replaces the deny rules.

Files move only through FastAPI.

1. FastAPI reads the object with its own storage key.
2. FastAPI writes the bytes through the host’s file API into `/input`.
3. The tool runs.
4. FastAPI reads `/output` through the same host API and stores plots and candidate tables itself.

A signed URL used from inside the sandbox would need network, so it contradicts the network rule. Short-lived signed URLs are allowed on the FastAPI side, where the API already holds credentials. The sandbox never sees the URL, the key, or the bucket name.

## 4. Resource limits

Targets are an 80,000-row table with fewer than 80 columns. A numeric frame of that size is on the order of tens of megabytes. String columns and a pandas copy during cleaning push it toward a few hundred megabytes. Two GiB covers a legitimate copy. It does not cover a cartesian explosion, and it should not.

| Limit | Value | What hits it | What the student sees |
| --- | --- | --- | --- |
| CPU | 2 vCPU, hard cap. `OMP_NUM_THREADS`, `OPENBLAS_NUM_THREADS`, and `MKL_NUM_THREADS` set to 1 | A tight statsmodels or pandas loop | The run is slower, then the wall clock kills it if it does not finish |
| Memory | 2048 MiB hard cap | A huge copy, an object-dtype explosion, a leak | The run fails. Partial files are discarded. The message says the working table did not fit. The app does not subsample in secret |
| Wall time | 120 seconds from process start | An accidental Python loop over rows, a solver that does not converge | The sandbox is killed. `result.json` is ignored even if a partial file exists. The log reason is `time_limit` |
| Output | Combined stdout and stderr 256 KiB. At most 12 files in `/output`. Images at most 8 MiB each. A candidate table at most 256 MiB. `result.json` at most 2 MiB | Printing the whole frame, writing an unbounded cross-join | FastAPI refuses the bundle. Nothing is stored as a result or as a new dataset version |
| Processes | Soft and hard `RLIMIT_NPROC` of 32, set by your wrapper before the tool starts | A fork bomb or a multiprocessing pool | Further forks fail and the run returns an error. Output is discarded |
| File size | `RLIMIT_FSIZE` of 256 MiB | A single file past the table cap | The write fails and the run is discarded |
| Disk | At least 2 GiB of sandbox disk, input plus output plus scratch | Packages already live in the image. This cap is for the run’s files | A write error fails the run |
| Network | Deny all egress | Any socket | The connection fails |

CPU is throttled rather than killed. Memory, wall time, process count, and output size end the run. On any of those endings FastAPI discards the bundle, writes a `sandbox_runs` row with the limit that fired, and does not ask the model to invent the missing table.

One hundred twenty seconds is enough for the spec’s procedures on 80,000 rows. If a real pilot run times out, raise this to 180 seconds. Do not raise it to the Hobby one-hour ceiling. That ceiling is the sandbox lifetime, not the tool budget.

At 2 vCPU and 2 GiB, a run that uses the full 120 seconds costs about half a cent on the E2B rates in the architecture note. Limits are a safety control first. They also keep a hostile or stuck run from mattering to the $1,120 budget.

## 5. Secrets

The sandbox environment contains only:

- `PATH` and `HOME` for the unprivileged user
- `MPLBACKEND=Agg`
- the three thread caps above
- `DATABUDDY_RUN_ID`, an id you generated, not a credential

It does not contain API keys, database URLs, object-storage keys, OAuth tokens, signed URLs, or the sandbox control-plane token. Do not pass a Modal Secret, an E2B `envs` entry copied from the API process, or an OIDC identity token into the sandbox.

Stdout, stderr, and tracebacks are capped and then redacted for common key patterns before they are stored or shown to the model. The approved source stored in Postgres is the script the student saw, not a dump of the environment.

## 6. Human control

These gates match the analytics spec. A sandbox run that fails a gate does not start.

| Run | Before the sandbox starts | After it returns |
| --- | --- | --- |
| Profile, whitespace trim, drop of fully empty rows and columns, lossless type coercion | No extra click. The student already asked to prepare this file. The step is logged and reversible. | Show the log. Undo replays the prefix. |
| `render_chart` | The student has confirmed the variables and the chart type from the analytics spec. The fixed function is the only code that runs. | Show the image. The dataset version does not change. |
| Assumption checks and a diagnostic plot for a method the student already selected | The selection is the approval. | Results bind to `result.json` and the image files. |
| Listwise deletion, imputation, outlier removal, recode, row filter, derived column, binning, ambiguous type change, sentinel-to-missing, duplicate drop, drop of a column that has data | The student confirms the operation and its parameters. Free-form source is not a substitute for that confirmation. | The working version changes only if they accept. |
| `run_comparison` or `run_regression` | The student has chosen the method, the variables, alpha, and one-sided or two-sided. The fixed function is the only code that runs. | The APA sentence is filled from `result.json`. |
| `transform_frame` | Show the full source. The student approves or edits it. FastAPI writes that exact string into the sandbox. | Show rows before and after, columns changed, and a short preview. The candidate becomes the working table only after a second accept when any values changed. |
| `custom_plot` | Show the full source and wait for approval. | Show the image. The dataset version does not change. |
| A method on the out-of-scope list | No sandbox. The decline is logged. | The consulting message from the analytics spec. |
| A subsample, a refit that drops influential rows, or a change of alpha | The student sets it before the run, in the open, before seeing the new p-value. | Logged as its own run. |

The model call ends while any of these waits. No sandbox is alive during the wait.

## 7. Threat model

Likelihood is for a ten-week, five-student pilot after the controls in this note are in place. Impact is what happens if that control is missing or bypassed.

| Threat | Likelihood with the controls | Impact if the control fails | Control |
| --- | --- | --- | --- |
| Data exfiltration via the network | Low. Both products default to allowing egress, so the create-time flag is a required test, not a default you can assume. | High. Microdata could leave the institution. | `allow_internet_access=False` on E2B, or `block_network=True` on Modal, on every create. No signed URL and no storage client inside the sandbox. Confirm the block covers DNS and IPv6, not only IPv4. |
| Reading another session’s files | Low, if every run is a new sandbox and the API copies one project’s keys. | High. Cross-tenant research data. | Fresh sandbox per tool run. No volumes and no pause snapshots. `/input` is read-only and contains only objects for this `institution_id` and `project_id`, chosen on the server. |
| Resource exhaustion | Medium. A bad script or a loop the model wrote is a normal pilot event. | Medium. That run dies. Cost stays small at the caps above. Many parallel runs could press the Hobby concurrency cap of 20. | The limits in section 4. Discard partial output. Five students do not approach 20 concurrent sandboxes unless a bug leaks sandboxes. Destroy on every exit path, including exceptions in FastAPI. |
| Prompt injection in a CSV cell | High that a cell will contain instruction-like text and that the model will see a sample. | High for the integrity of this project’s result. Low for other tenants, if isolation holds. | System prompt treats file contents as data. Fixed tools take validated column names, not interpolated source. Free-form source is approved by the student. Destructive diffs need a second accept. Out-of-scope methods have no free-form stats path. |
| Secrets leaking into logs | Low if section 5 is followed. Medium if the API environment is copied into the sandbox or a signed URL is placed in the script. | High. A storage key in a traceback is a bucket compromise. | Minimal environment. No Secrets and no OIDC token. Redact before persisting stdout. The control-plane token stays in the API process. |
| Persistence between sessions | Low if the sandbox is killed and volumes are unused. | High. A paused filesystem would carry one student’s files into a reused machine, or leave a snapshot you later resume by mistake. | `kill` on success, failure, and timeout. E2B lifecycle `on_timeout` is `kill`, not `pause`. Modal `volumes` and `network_file_systems` stay empty. Do not enable memory snapshots. |
| Official statistic computed by untested code | Low on the tight hybrid. High on option (c) or on a loose (b). | High for the capstone claim and for the student’s paper. A wrong p-value looks like a result. | FastAPI selects the fixed entrypoint for tests. `result.json` is the only statistics source. The free-form import hook refuses SciPy, statsmodels, and scikit-learn. |

## 8. E2B and Modal

Checked against the E2B Python SDK reference (create defaults) and the Modal Sandbox reference and networking guide. Re-check the flag names when you pin SDK versions. Both products change these defaults without changing the product name.

| Control | E2B | Modal | What you still do |
| --- | --- | --- | --- |
| Fresh sandbox per run | `Sandbox.create`, then `kill`. Hobby lifetime cap is one hour. Your tool cap is 120 seconds. | `Sandbox.create`, then `terminate`. Default lifetime is five minutes. Set `timeout=120`. | `try` / `finally` so an API exception cannot leave a sandbox up. |
| No outbound network | `allow_internet_access` defaults to `True`. Set `False`. That matches deny-all IPv4 egress. `update_network({})` clears rules you already set. | `block_network` defaults to `False`. Set `True`. It cannot be combined with an outbound allowlist. | One helper creates the sandbox. No other call site. Add a test that a socket in the sandbox fails. Confirm IPv6. |
| CPU and memory caps | Set on the template you boot. The create call used here does not take CPU and RAM. The account default is not this policy. Docs have disagreed between 512 MiB and 4 GiB. | `cpu` is in physical cores, and Modal counts one physical core as 2 vCPU. `memory` is MiB. Pass hard limits, `cpu=(1, 1)` and `memory=(2048, 2048)`, so the sandbox cannot burst past them. | Pin the E2B template at 2 vCPU and 2048 MiB and read back `cpu_count` and `memory_mb` at the start of each run. Fail the run if they differ. |
| Wall time | `timeout` on create, in seconds. Also kill from the API at 120 seconds so you do not depend on a pause lifecycle. | `timeout` on create, and `timeout` on `exec`. | Clock the run in FastAPI too. |
| No secrets in the environment | `envs` is whatever you pass. `secure=True` keeps the control-plane token on the host side. | `secrets` on `create` and on `exec` inject environment variables. `include_oidc_identity_token` defaults to false and must stay there. An outbound policy can attach header secrets. Do not configure one. | Pass the minimal environment from section 5. Unit-test the dict. |
| No persistent disk shared across users | `volume_mounts` exist. Leave them unset. `on_timeout` can `pause` and keep memory. Set `kill`. | `volumes` and `network_file_systems` exist, including cloud-bucket mounts. Leave them empty. Do not call snapshot APIs. | Code review the create helper whenever a new SDK option appears. |
| Read-only input and a single output folder | The file API writes bytes. It does not apply this layout for you. | The filesystem API writes bytes. Same gap. | Your wrapper creates `/input` and `/output`, marks `/input` read-only, and exits non-zero if the tool writes elsewhere. |
| Process and file-size caps | Not a create-sandbox parameter in the reference used here. | Not a create-sandbox parameter in the reference used here. | The wrapper sets `RLIMIT_NPROC` and `RLIMIT_FSIZE` before the tool starts. |
| Import allow-list | Not a product feature. | Not a product feature. | AST check in FastAPI, import hook in the free-form entrypoint. |
| Copy files without sandbox credentials | Host file API. | Host filesystem API. | FastAPI holds the storage key. The sandbox does not. |

E2B remains the host from the architecture note: one Firecracker microVM per sandbox is the isolation claim, and the Hobby plan fits the budget if every run is short and killed. Modal can enforce the same network, CPU, and memory switches, including a hard burst limit that you pass on create. Modal’s published runtime is either gVisor or a KVM virtual machine. Confirm which one your plan starts. Do not mount a Modal volume or a cloud bucket to “make file transfer easier.” That shortcut gives the sandbox a credential path this model forbids.

## What you verify on the first sandbox you boot

1. From inside the sandbox, a TCP connection and a DNS lookup both fail.
2. The process environment has no key, token, URL with a signature, or database string.
3. `/input` cannot be opened for write, and another project’s object key is not on the filesystem.
4. A second tool call has a new sandbox id. The first id is gone.
5. A free-form script that imports statsmodels fails before a fit, and `run_regression` still produces `result.json`.
6. A script that sleeps past 120 seconds yields no stored result.
7. E2B reports 2 vCPU and 2048 MiB. If you are on Modal, the hard limits match section 4.
