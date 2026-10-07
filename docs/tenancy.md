# DataBuddy v1 tenancy

A new university is rows in `institutions`, `institution_domains`, and `institution_settings`. It is not a schema, a deploy, or a code change. This note is the source of truth for that boundary. Object keys and usage rows already required `institution_id` in `docs/architecture.md`.

## 1. Tenancy approach

Use one Postgres database, `institution_id` on every tenant-owned row, and row-level security forced on those tables. The API connects as a role that does not own the tables and does not have `BYPASSRLS`.

Schema-per-tenant is the wrong tool at this scale. The pilot is one campus and about five students. The next step is a second campus, then a handful more. A shared schema means one migration, one connection pool, and one place to sum token use. A schema per university means a migration fan-out, a `search_path` you must get right on every request, and a solo developer operating N databases before there is anything to operate. It also does nothing for object storage. R2 has no row-level security, so the application still has to enforce the prefix `institution_id/project_id/...`.

Row-level security is what makes a forgotten `WHERE` fail closed. The request sets `app.institution_id`, `app.user_id`, and `app.role` with `SET LOCAL` inside the transaction, then the policy filters. `SET LOCAL` dies at commit, which is what a pooled connection requires. An empty setting matches no rows.

| | Shared database, `institution_id`, forced RLS | Schema per tenant |
| --- | --- | --- |
| New university | Insert three rows | New schema, grants, and a migration run |
| Forgotten filter | Policy returns nothing | A wrong `search_path` can return another campus |
| Platform usage totals | `SUM` grouped by `institution_id` | One query per schema |
| Fits one term and one VM | Yes | You would build a control plane you do not need |
| When it stops being enough | A campus contract that demands a separate database and its own restore | That contract, not the second campus |

The second campus turns on that campus’s budget. It does not change the schema. A dedicated database is future work for a contract that requires one, and it is a new budget, because it is a second Postgres to run.

## 2. How a user is mapped to an institution

The email in the verified Google or Microsoft token is the only email that matters. The address the browser sends is ignored. The domain is the lowercase part after `@`.

`institution_domains` holds one or more domains per institution. `uni.edu` and `students.uni.edu` are two rows pointing at the same institution. A domain belongs to at most one institution. Matching is exact. `cs.uni.edu` does not match a row for `uni.edu`.

On sign-in, in order:

1. If the user has an active membership whose `ends_at` is still in the future, the session uses that membership. Two active memberships at different institutions require the user to pick one. The session stores exactly one `institution_id`.
2. If the domain is approved and the institution is active, create a `student` membership and use it. This is the path for `@uni.edu` and `@students.uni.edu`.
3. Otherwise create nothing. The user can file an `access_requests` row. A personal mailbox and a domain the platform has never approved both land here.

Role assignment is not part of domain matching. Domain match creates `student` only. `institution_admin` is granted by a platform admin or by an institution admin of that same institution. `platform_admin` is a row in `platform_admins`, granted by another platform admin. The first platform admin is a bootstrap row you insert with a migration, not a domain rule.

Domain approval is a platform-admin action. An institution admin approves people into an institution that already exists. They do not attach a new domain. That split is what stops a campus admin from claiming another university’s domain.

Personal and consumer domains live in `blocked_email_domains`. That table is data. Approving a person with `@gmail.com` inserts a membership. It never inserts `gmail.com` into `institution_domains`.

## 3. Roles

A person is a row in `users`. Authority is a membership or a platform-admin row, not a column that follows them between universities.

| | Student | Institution admin | Platform admin |
| --- | --- | --- | --- |
| Projects | Create projects in the active institution. Read and change a project only when they are a project member. | List every project in the institution: title, owner, dates, token use. Read file bytes and row-level results only as a project member, or through break-glass. | No campus is in scope until they open a support session for one institution. That session is an audit row. Bytes still require break-glass. |
| Analysis | Run the tools in the analytics spec, inside their user quota and the institution budget. | Same, on projects they belong to. They can suspend a membership in the institution. | Set budgets, allowed models, retention ceiling, and region flags. They do not get a quiet path around the sandbox rules. |
| People | See members of their own projects. | Approve or reject access requests for their institution. Grant and revoke `student` and `institution_admin` there. | Create institutions. Approve domains. Grant the first institution admin. Decide access requests that have no institution yet. |
| Other institutions | No rows. | No rows. | List institutions, domains, and usage totals. Reading one campus’s data is a support session, not a default. |

Break-glass inserts a `project_members` row with `source = break_glass` and an `audit_log` row that stores the reason. It is the only way an admin reads a dataset they were not given. Removing that membership ends the access. The dataset stays where it is.

## 4. Institution settings

One row in `institution_settings` per institution. Platform ceilings live in `platform_settings`, a single row.

| Setting | Who can change it | Rule |
| --- | --- | --- |
| `token_budget_usd` | Platform admin | Institution cap for the period. The check is a sum of `usage_events` for that `institution_id`. The column exists now. Enforcement is on when `enforce_institution_budget` is true. The pilot campus gets a cap equal to the pilot model budget. The second campus is another row and another cap, not a code change. |
| `user_token_budget_usd` | Platform admin | Default per member. A membership may set a lower override. It cannot set a higher one. |
| `allowed_models` | Platform admin | Must be a subset of `platform_settings.allowed_models`. The API rejects a model id outside that subset before the provider call. |
| `retention_days` | Institution admin may shorten it. Platform admin sets it and is the only one who may lengthen it. | Cannot exceed `platform_settings.max_retention_days`. The retention job deletes object versions and the rows that point at them. The audit row that says the deletion ran is kept. |
| `region_code` and `allow_data_to_leave_region` | Platform admin | Pilot default is the region of the VM and the R2 bucket, with `allow_data_to_leave_region = true`. |

The region flag has to be honest about the stack you already chose. Prompts go to the Claude API and code runs in E2B or Modal. This pilot does not pin those providers to the bucket’s region. If an institution sets `allow_data_to_leave_region` to false, the API refuses uploads and analysis runs and tells the admin the current deployment cannot honor the pin. It does not ignore the flag. Region pinning is future work with its own cost. It is not a second schema.

## 5. Edge cases

**A student who transfers.** Set the old membership to `left`. Do not update `institution_id` on their old projects, files, or usage. Those rows were paid for and decided under the first campus, and they stay there. The new campus is a new membership and a new quota. The person can still sign in. They see the new campus only. They see the old campus only if that membership is still active, which it is not.

**A visiting researcher.** They are a `student` membership on the host institution with `starts_at` and `ends_at`. They are not a fourth role. Sign-in refuses the membership once `ends_at` has passed. A host project adds them through `project_members` after the membership exists. Their home university does not receive a copy of the dataset. When the visit ends, project access ends with the membership. The data remains the host’s.

**A shared lab dataset.** It is a project with more than one `project_members` row, all carrying the project’s `institution_id`. Sharing with someone who has no membership at that institution is a foreign-key failure, not a feature. Cross-institution collaboration is a visit: membership on the host, then a project seat. There is no project that belongs to two institutions.

**A personal email address.** The domain is in `blocked_email_domains`, so it cannot be approved as an institution domain. The person files an access request and names the campus. That campus’s institution admin, or a platform admin, approves it and the result is a normal membership. The same queue handles `@new-university.edu` before anyone has onboarded that domain. A platform admin who wants every future address at that domain to match must approve the domain as its own action. Approving one person does not approve the domain.

## 6. Entity-relationship description

Global tables have no tenant. Everything a student creates is tenant-owned and carries `institution_id`.

```text
platform_settings ||--|| (single row: model allow-list, max retention, home region, region pin available)
blocked_email_domains ||--o{ domain

institutions ||--|| institution_settings
institutions ||--o{ institution_domains
institutions ||--o{ memberships
institutions ||--o{ projects
institutions ||--o{ access_requests

users ||--o{ memberships
users ||--o| platform_admins
users ||--o{ access_requests
users ||--o{ project_members

projects ||--o{ project_members
projects ||--o{ files
projects ||--o{ dataset_versions
projects ||--o{ cleaning_log
projects ||--o{ analyses
projects ||--o{ sandbox_runs
projects ||--o{ usage_events

files ||--o{ dataset_versions
analyses ||--o{ decisions
analyses ||--o{ sandbox_runs

deletion_outbox }o--|| institutions
audit_log }o--|| users
support_sessions }o--|| institutions
```

`users` is global because one person can be a student at one campus and later at another. `platform_admins` is global for the same reason. `institution_domains.domain` is unique across the whole table. `memberships` is unique on `(user_id, institution_id)` while `status = active`.

Tenant-owned tables, each with `institution_id NOT NULL` and a foreign key to `institutions`: `institution_settings`, `institution_domains`, `memberships`, `projects`, `project_members`, `files`, `dataset_versions`, `cleaning_log`, `analyses`, `decisions`, `sandbox_runs`, `usage_events`, `out_of_scope_events`, `deletion_outbox`, `support_sessions`. `access_requests.institution_id` is nullable until someone resolves the request. `audit_log.institution_id` is nullable only for a platform action that is not inside a campus, such as creating the institution row.

`project_members.institution_id` is denormalized so the policy can filter without hopping through a table the role cannot see. It must equal `projects.institution_id`. Object keys are `institution_id/project_id/file_id`. The key is written by the API from the session, not from the client.

Row-level security is forced on every tenant-owned table. The runtime roles are `databuddy_app` for HTTP requests and `databuddy_worker` for the deletion outbox. Neither owns the tables. Neither has `BYPASSRLS`. The worker’s grants are limited to `deletion_outbox`. HTTP policies fail closed when `app.institution_id` is unset.

Policy shape:

- Student: `institution_id` equals the session institution, and the row’s project is one they belong to. Usage rows are further limited to their own `user_id`.
- Institution admin: same institution, all projects for metadata and usage, and file bytes only where a `project_members` row exists for them.
- Platform admin on ordinary requests: no tenant rows. On a support session: the same institution filter as an institution admin, with the support session id written to `audit_log`.
- Inserts and updates: `WITH CHECK` uses the session institution. A client-supplied `institution_id` that differs is rejected.

## 7. Invariants

These are the statements the tests should pin. A test that only checks the happy path is not enough. Each invariant needs a case that tries to break it.

1. A query, insert, update, or delete under institution A returns and changes no row whose `institution_id` is B. This includes a request that sends B’s id in the body, the query string, or a cookie the client forged.
2. With `app.institution_id` unset, every tenant table returns zero rows and accepts zero writes.
3. The database roles used by FastAPI and the worker are not superusers, do not own the tenant tables, and do not have `BYPASSRLS`.
4. `SET LOCAL` is cleared at the end of the transaction. A second checkout of the same pooled connection does not still carry the previous institution.
5. A domain string maps to at most one institution. Approving `students.uni.edu` does not authorize `@uni.edu`, and the reverse is also false.
6. No domain in `blocked_email_domains` can appear in `institution_domains`. Approving a Gmail user creates a membership and does not create a domain row.
7. Domain match creates a `student` membership only. It never creates `institution_admin` or `platform_admin`.
8. A user with no active, unexpired membership and no approved domain has no `institution_id` in the session and cannot create a project, upload a file, or start a model call.
9. A session contains exactly one `institution_id`. A second active membership is reachable only by an explicit switch that writes a new session.
10. After a membership is `left`, that user no longer reads that institution’s projects, and no project, file, analysis, or usage row has moved to the new institution.
11. A membership with `ends_at` in the past cannot be used to sign in, list projects, or open a sandbox.
12. Every `project_members.institution_id` equals the parent project’s `institution_id`. Inserting a member from another institution fails.
13. A project has exactly one institution for its whole life.
14. An institution admin’s request does not return file bytes or analysis result payloads for a project where they have no `project_members` row. Break-glass creates that row and an audit row, or it does not grant the read.
15. A platform admin token without an open support session reads no student files and no analysis payloads. Usage totals and institution records are the cross-tenant surface.
16. `institution_settings.allowed_models` is a subset of the platform allow-list. A model outside that subset never reaches the provider.
17. A membership’s user budget override is less than or equal to the institution’s `user_token_budget_usd`.
18. A model call is refused when the user’s summed usage for that institution would exceed their budget. When `enforce_institution_budget` is true, the same call is refused when the institution sum would exceed `token_budget_usd`.
19. `retention_days` is never greater than the platform maximum. An institution admin’s update cannot increase it.
20. When `allow_data_to_leave_region` is false, upload and analysis return an error and write no object and no sandbox run.
21. Every object key starts with the session’s `institution_id` and the project id. A key for another institution is not requested from R2 on a user-facing path.
22. The sandbox copy contains only objects whose keys passed invariant 21 for this run. The sandbox environment still has no storage credentials, per the threat model.
23. `usage_events`, `cleaning_log`, `decisions`, `sandbox_runs`, and `out_of_scope_events` rows include the session’s `institution_id` and `user_id`. A decline writes a row and does not write a result payload from another campus.
24. Deleting a project deletes or outboxes only object keys under that project’s prefix, and the outbox worker’s database grants do not include `SELECT` on analysis payloads.

## Defense notes

Shared tables plus forced row-level security make “no query returns another institution” a database rule instead of a habit in the route handlers. A new university is a domain row and a settings row, which is what “many universities without code changes” has to mean for one developer on one VM.

Memberships are separate from the person so a transfer or a visit changes access without rewriting history. The dataset stays with the institution that owned it when the work was done, and a personal mailbox can be approved onto a campus without turning Gmail into a tenant.