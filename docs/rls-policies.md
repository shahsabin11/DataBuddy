# RLS policy cheat sheet

One line each. Policies apply to `databuddy_app`. Platform admins use `databuddy_admin` (BYPASSRLS) instead.

| Policy | Table | Meaning |
| --- | --- | --- |
| `institutions_select` | institutions | Read only the campus in `app.institution_id`. |
| `institutions_deny_write` | institutions | App role cannot create or alter campuses. |
| `users_select` | users | See yourself, or (as institution_admin) users with a membership on your campus. |
| `users_update_self` | users | Update only your own profile row. |
| `platform_admins_deny_app` | platform_admins | Platform-admin grants are invisible to the app DB role. |
| `blocked_email_domains_select` | blocked_email_domains | Anyone authenticated may read the blocked-domain list. |
| `blocked_email_domains_deny_write` | blocked_email_domains | Only the admin DB role may change blocked domains. |
| `platform_settings_select` | platform_settings | Anyone authenticated may read platform ceilings. |
| `platform_settings_deny_write` | platform_settings | Only the admin DB role may change platform ceilings. |
| `institution_domains_select` | institution_domains | Read email domains for your campus only. |
| `institution_domains_deny_write` | institution_domains | Domain approval is a platform-admin (admin DB role) action. |
| `institution_budgets_select` | institution_budgets | Read your campus token budget and settings. |
| `institution_budgets_deny_write` | institution_budgets | Budget changes go through the admin DB role. |
| `memberships_select` | memberships | Students see their own memberships; campus admins see all on campus. |
| `memberships_admin_write` | memberships | Only institution_admins may grant/suspend memberships on their campus. |
| `projects_select` | projects | Students see projects they belong to; admins see all campus project metadata. |
| `projects_insert` | projects | Create a project only for your campus, with yourself as owner. |
| `projects_update` | projects | Update a project only if you are a project member on your campus. |
| `projects_delete` | projects | Delete only projects you own on your campus. |
| `project_members_select` | project_members | See membership rows for your campus (students: projects they are on). |
| `project_members_write` | project_members | Add/remove members only on your campus when admin or already a member. |
| `datasets_*` | datasets | CRUD only when `institution_id` matches and you are a project member (admins included only if members). |
| `dataset_versions_*` | dataset_versions | Same project-member rule — cleaning history is student data. |
| `analysis_sessions_*` | analysis_sessions | Same project-member rule. |
| `agent_steps_*` | agent_steps | Same project-member rule — code and tool output stay with the project. |
| `artifacts_*` | artifacts | Same project-member rule — plots/tables/reports are student data. |
| `usage_ledger_select` | usage_ledger | Students see their own spend; institution_admins see the campus aggregate. |
| `usage_ledger_insert` | usage_ledger | Record usage only as yourself on your campus. |
| `usage_ledger_deny_mutate` | usage_ledger | Usage rows are append-only for the app role. |
| `usage_ledger_deny_delete` | usage_ledger | Usage rows cannot be deleted by the app role. |
