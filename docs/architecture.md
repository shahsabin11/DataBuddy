# DataBuddy v1 architecture

The stack below is the one already chosen. This note checks that the layers fit, records the three decisions still open inside that stack, and tests the result against the $1,120 term budget.

Chosen layers:

- Frontend: Next.js, TypeScript, Tailwind. Chat workspace with upload, conversation, charts, and results panels.
- API: FastAPI. Same language as the analysis code (pandas, statsmodels, scikit-learn).
- Agent: Claude Agent SDK or LangGraph, with a small explicit toolset. Recommendation in section 3.
- Sandbox: E2B or Modal. Recommendation in section 3. Autonomy, isolation, and limits are in `docs/threat-model.md`.
- Data and auth: Postgres and S3-compatible object storage (Cloudflare R2 or S3). Google and Microsoft sign-in. Institution comes from the email domain, with a mapping table. Every user, project, file, and usage row carries `institution_id`. The tenancy rules are in `docs/tenancy.md`.
- Deploy: Docker Compose on a small VM, Fly.io, or Render. No Kubernetes.
- Metering: per-user token quotas in the pilot. Per-institution quotas turn on when a second campus joins. The rows store both ids from day one.

v1 analysis stays inside `docs/analytics-spec.md`. The tool list is that spec. scikit-learn may be installed for a tool implementation you wrote. It is not a second analysis product, and the agent does not get a tool that can import an arbitrary estimator.

## 1. Architecture summary

A student signs in with Google or Microsoft. FastAPI resolves the email domain through `institution_domains` and opens a session bound to one institution. The browser uploads a CSV or XLSX to FastAPI, which stores the bytes in object storage and a metadata row in Postgres. The original object is never overwritten. In the chat workspace the student states a research question or asks for a chart. FastAPI runs a short agent graph whose only actions are the named tools. On a judgment step the graph stops and the student chooses, including which chart type to draw. On a computation step FastAPI copies that one file into a fresh sandbox, runs the tool there with no network and a resource cap, and writes tables and plots back to Postgres and object storage. A chart can be saved without a model. The workspace renders the stream as it arrives. Token use is recorded on the user, and on the institution, before the quota allows another model call.

### Request flow

1. Sign-in. The browser completes Google or Microsoft OAuth. FastAPI keeps the identity-provider tokens on the server, issues its own session cookie, and sets `institution_id` from `institution_domains`. An unmapped domain, including a personal mailbox, stops at an invite code that a campus admin has tied to an institution. One university can own several domains.
2. Upload. Next.js posts the file to FastAPI. FastAPI inserts a `files` row as `pending`, writes the object to `institution_id/project_id/file_id`, then marks the row `ready`. A failed upload leaves a row the sweeper can see. The sandbox never receives storage credentials.
3. Plan. The student sends a message. Next.js opens a same-origin server-sent-events stream to FastAPI. The agent loads this project’s checkpoint, appends the message, and either calls one tool or pauses for a decision. The pause is the chart type, the method choice, the variable types, a destructive clean, or alpha. The model call ends there. Nothing is billed while the student thinks, and no sandbox is left running.
4. Execute. For a compute tool, FastAPI reads the object with its own key, copies the bytes into a new sandbox, and starts the run with network disabled and CPU, memory, and time limits. The sandbox process is the only place pandas and statsmodels run. FastAPI does not execute model-written code on the API host.
5. Return. Tables and the decision record (recommendation, alternatives, the option the student picked) go to Postgres. Plots go to object storage. FastAPI streams typed events to the workspace: text, tool started, tool finished, needs decision, run complete. The sandbox is destroyed at the end of the tool call.
6. Meter. Each Claude response writes `usage_events` (`institution_id`, `user_id`, model, uncached input, cache read, output). The next model call is refused when that user is over the pilot quota.

Same-origin routing is part of the flow. The reverse proxy sends `/` to Next.js and `/api` to FastAPI, so the session cookie stays first-party.

## 2. How the pieces fit

| Boundary | What crosses it | What stays behind it |
| --- | --- | --- |
| Browser ↔ FastAPI | File bytes, chat messages, SSE events, session cookie | Identity-provider tokens, storage keys, service credentials |
| FastAPI ↔ Postgres | Users, projects, cleaning log, decision record, usage | File bytes |
| FastAPI ↔ object storage | Original upload, plot images | Queries and quotas |
| FastAPI ↔ Claude | Tool schemas, the research question, sandbox results already produced | Raw credentials, other tenants’ rows, the storage key |
| FastAPI ↔ sandbox | One student’s file and one tool run | Network, storage credentials, any other project’s data |

The explicit toolset is what makes the agent layer and the analytics spec the same surface. Fixed tools (`profile_table`, `apply_confirmed_clean`, `render_chart`, `run_comparison`, `run_regression`, and the diagnostic plots that belong to a chosen test) are code you wrote. `render_chart` draws a histogram, box plot, bar chart, grouped bar, heatmap, or scatter plot the student confirmed, with no model required. Two free-form tools, `transform_frame` and `custom_plot`, may run pandas and matplotlib after the student approves the source. They cannot produce the statistics in the report. That split is specified in `docs/threat-model.md`.

Postgres is the system of record for who decided. Object storage is the system of record for bytes. The agent checkpoint stores the graph position so a student can close the laptop on a decision step and resume.

## 3. The three open choices

### 3a. Claude Agent SDK or LangGraph

Both run inside FastAPI and bill Claude tokens. Neither choice adds a required second AI vendor. Claude Managed Agents, the hosted runtime at $0.08 per session-hour, is a different product and is not one of the two options.

| | Claude Agent SDK | LangGraph |
| --- | --- | --- |
| Shape | Tool loop aimed at finishing a task | Graph you draw: nodes, edges, and pauses |
| Fit to “student decides” | You must add stop rules so the loop does not pick the test itself | A pause is a node. The run cannot pass it without the student’s answer |
| Tool surface | Ships with a coding-agent tool set you would turn off | Starts empty. You register the spec’s tools |
| Where it runs | In the API process, with your API key | In the API process. Checkpoints sit in the same Postgres |
| Extra fee | None on an API key. A personal Claude subscription credit is not the app’s meter | Library is free. LangSmith Plus is $39 per seat per month and is optional |
| One-term cost | Less structure to invent, more discipline to keep the loop inside the spec | More design up front, and that design is the capstone argument |

Recommendation: LangGraph, self-hosted in FastAPI, checkpoints in Postgres, no LangSmith paid plan. The pilot is a sequence of required pauses, and the graph is the record of those pauses. Use the Claude API from that graph. Keep LangSmith off unless the free Developer tier (5,000 base traces per month on the current LangSmith page) is enough for your own debugging.

### 3b. E2B or Modal

Unit cost is small either way at five students. The plan floor and the isolation model are the decision. Full image and policy design is the next note. This row assumes each tool call gets a new sandbox that is destroyed when the call returns, so a chat that lasts longer than an hour does not need a sandbox that lasts that long.

Published usage rates used here:

- E2B, from the pricing page: $0.000014 per vCPU-second ($0.0504 per vCPU-hour) and $0.0000045 per GiB-second ($0.0162 per GiB-hour). Hobby is $0 per month, with a one-time $100 usage credit, 20 concurrent sandboxes, and a one-hour session cap.
- Modal Sandboxes, from the pricing page: $0.00003942 per physical-core-second (Modal defines that core as 2 vCPU) and $0.00000667 per GiB-second. Starter has no monthly fee and includes $30 of compute per month.

A 2 vCPU, 2 GiB sandbox for one hour is about $0.13 on E2B and about $0.19 on Modal. Sixty hours across build and pilot is on the order of $8 and $12. Both sit inside the published credits if those credits apply to sandbox time. Confirm that on the day you create the account.

| | E2B Hobby | Modal Starter |
| --- | --- | --- |
| Isolation | Firecracker microVM, one kernel per sandbox | Modal’s sandbox runtime. GPU-capable, which v1 does not use |
| Pilot bill | Usage against a one-time $100 credit, then the hourly rate. Pro is $150 per month and is for the 24-hour session limit and higher concurrency | Usage against a renewing $30 monthly compute credit, then the sandbox rate |
| Session cap | One hour on Hobby | No Hobby-style one-hour cap in the figures above |
| Why it can still fit | Tool calls are minutes, then the sandbox is destroyed | The renewing credit covers the pilot’s compute |

Recommendation: E2B Hobby. Model-written code is the threat this layer exists for, and a per-run microVM is the isolation story the capstone can defend. The one-hour Hobby cap is satisfied by destroying the sandbox at the end of each tool call. E2B Pro at $150 per month does not fit this budget. E2B’s `allow_internet_access` defaults to on. Every create sets it to off, as required by `docs/threat-model.md`.

### 3c. Fly.io, Render, or a small VM

The app is four processes: reverse proxy, Next.js, FastAPI, Postgres. Files are in R2, so the VM disk holds the database and the containers, not the CSVs. Paid hosting is required so a demo does not wait on a free-tier sleep.

Prices cited from vendor pages on this pass: Fly.io’s 1 October 2026 price update lists `shared-cpu-1x` with 256 MB at $2.19 per month and Managed Postgres Basic at $38 per month plus $0.28 per GB. The Fly docs example prices a `shared-cpu-1x` with 1 GB at $6.70 per month. Render’s current price page was not re-fetched here. Secondary comparisons in 2026 put a paid Starter web service at $7 per month (512 MB) and a small Render Postgres near $6 to $19 per month. Verify Render before using it. The VM line uses $12 per month as a conservative planning figure for a 2 GB instance, not a live quote.

| | Small VM and Docker Compose | Render paid | Fly.io |
| --- | --- | --- | --- |
| What you run | Proxy, Next.js, FastAPI, Postgres in one Compose file | A web service per process, plus Render Postgres | Machines for the apps. Managed Postgres is a separate $38 plan |
| Cold start | None while the VM is on | None on the paid web services | None while the Machine is started |
| Ops you own | OS updates, TLS, disk backup to R2 | Platform patches. You still own backups of a small database | `fly.toml`, volumes, and Postgres yourself if you refuse the $38 plan |
| Six-month compute shape | About $12 × 6, plus a domain | On the secondary figures, two Starter services and a small database land around $20 to $33 per month | App Machines can stay under $15. Adding Managed Postgres Basic moves the floor to about $47 before storage |
| Cookie story | One host, first-party session cookie | Same if one service proxies the other. Harder if the site and the API are different origins | Same constraint |

Recommendation: one small always-on VM, 2 GB of RAM, Docker Compose, Let’s Encrypt, Postgres in Compose, nightly `pg_dump` uploaded to R2. That is the deployment already implied by Compose, the cookie stays first-party, and six months of host cost stays near $72 at the $12 planning figure. Render paid is the alternative if you want the platform to own the OS. Fly Managed Postgres at $38 per month is the option that does not fit the term budget. A self-managed Postgres Machine on Fly is a second system to learn for the same database Compose already runs.

Object storage recommendation inside the chosen layer: Cloudflare R2. Published Standard rate is $0.015 per GB-month with no egress fee, and the public free allowance cited for Standard is 10 GB-month plus a large free operation quota. S3 Standard is $0.023 per GB-month in us-east-1 and adds egress. At pilot size the storage bill is about zero on either one. R2 avoids an egress line when the API and the browser read plots.

## 4. Integration risks

| Risk | What goes wrong | How v1 handles it |
| --- | --- | --- |
| Getting a file into the sandbox | A storage key inside the sandbox lets generated code read every object. A presigned URL fetched from inside the sandbox requires network, which this design turns off | FastAPI reads the object with its own key and copies bytes in through the sandbox file API. The run then starts with no network. Only that file is copied |
| Streaming the agent to Next.js | A proxied request that buffers until the graph finishes leaves the UI silent, and a cross-origin socket complicates the cookie | Server-sent events on `/api`, same origin as the site. Events are typed: text delta, tool started, tool finished, needs decision, error, done. A decision event closes the model call. The next student message starts a new stream from the checkpoint |
| OAuth across the two apps | Putting the Google or Microsoft token in the browser, or trusting an email domain as a complete institution id, breaks the tenant boundary. Personal mail and a university with two domains are normal | Authorization-code flow. Provider tokens stay on the API. The browser gets an httpOnly session cookie. `institution_domains` maps many domains to one institution. Unmapped domains require an invite bound to an institution. Every query and every object key includes `institution_id` from the session, not from the client |
| Postgres and object storage on delete | Deleting the row first orphans the object. Deleting the object first leaves a row whose download 404s. A crash between the two is ordinary | Upload: row `pending`, put object, row `ready`. Delete: row `deleting` plus an outbox key, delete the object, then drop the row. A periodic job retries outbox keys. Project delete walks the cleaning log and the plot keys the same way. The original upload is removed only as part of that project delete |
| Quota bypass | A streamed run that checks the quota after the model call can overshoot, and a second campus is invisible if usage rows lack `institution_id` | Check and reserve before the call. Commit the actual token counts when the response finishes. Release the reserve on failure. Institution totals are a sum over rows that already have `institution_id`. The second campus adds a cap on that sum |
| Code running on the wrong machine | The convenient path is `exec` inside the API container. That puts student data and model-written code next to the database password | The API process has no analysis runner. Compute tools know how to copy a file in and start a sandbox. Import allowlists live in that runner so a prompt cannot load an out-of-scope estimator even though the image contains scientific Python |
| Waiting with a live sandbox | A sandbox held open while the student reads a recommendation burns the E2B hour cap and blurs tenants across turns | Create the sandbox at the start of a compute tool and destroy it before the decision event is sent |
| Charts and tables disagreeing | The model narrates numbers it did not receive | The report panel binds to the sandbox result rows. The model receives those rows as tool output and writes the explanation around them |

## 5. Cost check

Window: six months, matching the Cursor line. The pilot inside that window is 10 weeks, 5 students, 8 sessions per student per week, which is 400 sessions. Infrastructure is paid for all six months so build demos stay awake.

The dollar amounts on the budget lines were blank in the request. The split below is the one that adds to $1,120 and still covers the expected bill. Replace it if you already had different line amounts in mind.

| Line | Proposed amount | What it has to pay |
| --- | --- | --- |
| Dev and test model usage | $450 | API tokens while building. Separate from Cursor |
| Cursor Pro, 6 × $20 | $120 | Your editor. Stated by you. Not the app’s meter |
| Pilot model usage | $250 | 400 student sessions, with headroom |
| Paid infrastructure for the term | $180 | VM, domain, object storage, sandbox past the credit |
| Domain and small tools | $20 | Registration. Folded here so it is not double-counted against infrastructure |
| Contingency | $100 | A heavy debugging week, or a model rate higher than the one quoted |
| Total | $1,120 | |

Infrastructure at $180 is larger than the expected VM bill on purpose. The extra is the sandbox credit running out, a price you still need to confirm, and backups.

### Model price used

From the Claude API pricing page, retrieved for this note: Claude Sonnet 5 is $2 per million input tokens and $10 per million output tokens. Cache reads are $0.20 per million. The page’s footnote says the increase to $3 / $15 that had been scheduled for 1 September 2026 did not happen, and $2 / $10 is the standard price. Haiku 4.5 is $1 / $5, with cache reads at $0.10. Opus-class models are several times this rate and are outside the budget.

### Expected session cost

Assumption, not a published price. One student session is 10 Sonnet 5 calls. Each call carries 8,000 cached input tokens, 10,000 uncached input tokens, and 1,000 output tokens.

- Cache read: 8,000 / 1,000,000 × $0.20 = $0.0016
- Uncached input: 10,000 / 1,000,000 × $2 = $0.0200
- Output: 1,000 / 1,000,000 × $10 = $0.0100
- Per call: $0.0316
- Per session: $0.32
- 400 sessions: about $130

A session with no prompt caching and twice the calls is about $1.00, and 400 of those are about $400. That still fits the $250 pilot line only if most sessions stay near the first assumption. The $100 contingency covers a bad week, not a whole pilot at the heavy rate. Pin Sonnet 5, cache the system prompt and the tool schemas, and keep the graph from retrying in a loop.

Dev usage is budgeted at $450, about three and a half times the expected pilot token bill. That matches the constraint that building the agent costs more tokens than the students do. If the first month of API invoices is already past roughly $75, cut trace volume and caching before the term is half over.

Per-user pilot quota that fits the $250 line: $50 per student for the 10 weeks. Expected use at $0.32 a session and 80 sessions is about $26, so the cap is a little under two times expected use. The check is in FastAPI, in dollars or in token-equivalents of Sonnet 5, using `usage_events`.

### Monthly infrastructure at pilot scale

| Component | Expected monthly cost | Six-month cost | Basis |
| --- | --- | --- | --- |
| VM, 2 GB, always on | $12 planning figure | $72 | Not a live quote. Confirm on the host’s calculator |
| Postgres | $0 extra | $0 | Runs in Compose on that VM. Dump to R2 nightly |
| Cloudflare R2 | $0 inside the free allowance | $0 | Pilot bytes are a few GB. Confirm the 10 GB Standard allowance |
| E2B Hobby | $0 until the $100 credit is gone, then about $0.13 per 2 vCPU / 2 GiB hour | Under $15 of usage if the credit is exhausted | 60 hours of sandbox time is about $8 at the published rate |
| Domain | about $1 to $2, billed yearly | $10 to $15 | Depends on the name. Confirm at the registrar |
| Google and Microsoft OAuth | $0 | $0 | App registration only |
| LangGraph | $0 | $0 | Self-hosted. No LangSmith Plus |
| Claude API | see the session math | Dev $450 line, pilot about $130 expected | Sonnet 5 list price |

Expected infrastructure cash for six months is about $90. The $180 line covers it. Expected model cash is about $130 of pilot usage plus whatever portion of the $450 you actually burn in development. The budget covers the expected case.

It does not cover these switches:

- E2B Pro at $150 per month, or six months of that plan
- Fly Managed Postgres Basic at $38 per month on top of the app Machines
- LangSmith Plus at $39 per seat per month
- Claude Managed Agents session-hour fees stacked on a second sandbox bill
- An Opus-class model as the default for every turn

### Numbers to verify yourself

These are the figures this note depends on. Re-open the vendor page before you buy the annual domain or the first API credits.

1. Claude Sonnet 5 at $2 / $10 per million, and cache reads at $0.20, on the Claude API pricing page. Re-read the footnote that cancelled the 1 September 2026 increase.
2. Haiku 4.5 at $1 / $5 if you later move mechanical narration off Sonnet.
3. E2B Hobby: $0 plan, one-time $100 credit, 20 concurrent sandboxes, one-hour cap, $0.0504 per vCPU-hour, $0.0162 per GiB-hour. The docs disagree on the default RAM (512 MiB in the pricing FAQ, 2 vCPU and 4 GiB on the pricing page). Confirm the default, and confirm that usage past the $100 credit bills in place rather than forcing Pro.
4. Modal sandbox rates, only if you reopen that choice: $0.00003942 per physical-core-second and $0.00000667 per GiB-second, and the Starter $30 monthly compute credit.
5. Fly.io, only if you reopen that choice: the 1 October 2026 machine table and Managed Postgres Basic at $38 per month.
6. Render’s price page, which was not re-fetched for this note. Do not treat the $7 Starter figure as confirmed.
7. The VM provider’s price for a 2 GB instance. The $12 figure is a ceiling used so the budget still works if the host is at the expensive end of “small.”
8. Cloudflare R2’s free Standard allowance and the $0.015 per GB rate.
9. The registrar’s price for the exact domain.
10. Actual tokens per session after the first week of real runs. Replace the 10-call assumption with that invoice.

## 6. When this stack has to change

The pilot does not need a different architecture. These are the thresholds worth putting under future work.

| Signal | What is still fine | What changes |
| --- | --- | --- |
| Second campus | Same schema. Usage rows already have `institution_id` | Turn on the institution cap as a sum. Add that campus’s domains to `institution_domains`. No new service |
| Concurrent code runs | E2B Hobby allows 20 concurrent sandboxes. Five students in a seminar stay under that | Above 20 concurrent runs, or a real need to hold one sandbox open for more than an hour, the next step is E2B Pro at $150 per month. That needs a new budget, not a new vendor |
| Concurrent chats on the API | A 2 GB VM running the proxy, Next.js, FastAPI, and Postgres is sized for a seminar and a demo, on the order of 25 live streams | Past that, move to a larger VM and keep Compose. Kubernetes is still the wrong change |
| Database durability | Nightly dumps to R2 are enough for one pilot campus you can restore yourself | A second campus that expects point-in-time recovery is the point to add managed Postgres. Fly’s Basic plan at $38 per month is the published price of that step. Budget for it then |
| Analysis product | The explicit tools cover the analytics spec | A new method family (mixed models, time series, anything the spec declines) is a product decision. The host, the sandbox vendor, and the graph runtime can stay |
| Model bill | Sonnet 5 with caching fits the $250 pilot line at the assumed session size | If invoices show about $1 a session, the change is fewer calls and more caching, still on this stack. A larger default model is a budget change first |

## Defense notes

The sandbox runs only the file FastAPI copied in, with the API holding the storage credentials and the identity-provider tokens. Generated code never sits on the machine that has the database password. That split is what makes “the model can write the analysis” compatible with “a student cannot reach another institution’s data.”

`institution_id` is a column on the session, the project, the file, the cleaning log, the decision, and the usage event, and it is the prefix of every object key. The second campus is a row in `institutions` plus a quota. It is not a fork of the app, and it does not depend on every student sharing one email domain, because unmapped domains come in through an invite.

The graph’s decision nodes are the human-in-the-loop rule from the analytics spec. The agent can recommend a test. The transition into `run_comparison` or `run_regression` happens after the student’s selection is stored. A sandbox that is destroyed before that pause cannot keep working on a choice the student has not made.
