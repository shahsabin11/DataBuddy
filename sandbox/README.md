# DataBuddy E2B sandbox template

Per [`docs/architecture.md`](../docs/architecture.md) and
[`docs/threat-model.md`](../docs/threat-model.md):

- One fresh sandbox per tool run, then destroy
- `allow_internet_access=False` on every create (set by the API, not this image)
- No secrets in the environment
- Fixed entrypoints in `databuddy_sandbox/` produce `/output/result.json`
- Free-form code may use only the allow-list in `allowlist.py`

## Build the template

```bash
# Install once: npm i -g @e2b/cli   or   pip install e2b-cli
export E2B_API_KEY=...
cd sandbox
e2b template build
```

Copy the printed template id into `.env` as `E2B_TEMPLATE_ID`.

## Local smoke test of the helper library

```bash
cd sandbox
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
mkdir -p /tmp/db-in /tmp/db-out
printf 'a,b\n1,2\n3,4\n' > /tmp/db-in/data.csv
# entrypoints expect /input and /output; override for a quick import check:
python -c "from databuddy_sandbox.allowlist import is_import_allowed; assert is_import_allowed('pandas')"
```

The API copies student files into `/input` and collects `/output` after each run.
