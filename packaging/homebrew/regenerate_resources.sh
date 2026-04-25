#!/usr/bin/env bash
# Regenerate the Python `resource` blocks in llmind-cli.rb.
#
# Why not `brew update-python-resources`? Brew pins pip to
# `--uploaded-prior-to=<24h ago>` for reproducible builds. That works for
# homebrew-core but breaks personal taps: any flux in the dep tree at the
# cutoff makes pip's dry-run fail with no actionable error. This script
# bypasses that constraint by using pip's plain --dry-run --report and then
# querying the PyPI JSON API for sdist URLs.
#
# Run after bumping any version in llmind-cli/pyproject.toml's
# [project.dependencies] or [project.optional-dependencies] (anthropic,
# openai, gemini). Commit the resulting formula change.
#
# Requires: python3.11+, curl, jq-not-needed (uses python json).

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
CLI_DIR="$ROOT/llmind-cli"
FORMULA="$ROOT/packaging/homebrew/llmind-cli.rb"

# 1. Build a fresh sdist of llmind-cli.
WORK=$(mktemp -d)
trap 'rm -rf "$WORK"' EXIT

cd "$CLI_DIR"
python3 -m venv "$WORK/venv"
"$WORK/venv/bin/pip" install --quiet --upgrade pip build
"$WORK/venv/bin/python" -m build --sdist --outdir "$WORK/dist" >/dev/null
SDIST=$(ls "$WORK/dist"/llmind_cli-*.tar.gz | head -n 1)

# 2. Resolve full dep tree with cloud providers (no --uploaded-prior-to).
"$WORK/venv/bin/pip" install --dry-run --ignore-installed \
  --report="$WORK/report.json" \
  "${SDIST}[anthropic,openai,gemini]" >/dev/null

# 3. For each non-llmind-cli package, query PyPI for the sdist URL + SHA256.
"$WORK/venv/bin/python" - "$WORK/report.json" "$WORK/resources.rb" <<'PY'
import json, sys, urllib.request, ssl

with open(sys.argv[1]) as f:
    report = json.load(f)
out = open(sys.argv[2], "w")

# certifi-validated context (system Python often missing root certs on macOS)
try:
    import certifi
    ctx = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    ctx = ssl.create_default_context()

blocks = []
for pkg in report["install"]:
    name = pkg["metadata"]["name"]
    version = pkg["metadata"]["version"]
    if name.lower() == "llmind-cli":
        continue
    url = f"https://pypi.org/pypi/{name}/{version}/json"
    for attempt in range(5):
        try:
            with urllib.request.urlopen(url, timeout=30, context=ctx) as r:
                data = json.load(r)
            break
        except Exception as e:
            if attempt == 4:
                raise SystemExit(f"failed to fetch {name}=={version}: {e}")
    sdist = next((u for u in data["urls"] if u["packagetype"] == "sdist"), None)
    if not sdist:
        raise SystemExit(f"no sdist on PyPI for {name}=={version}")
    blocks.append((
        name.lower(),
        f'  resource "{name}" do\n'
        f'    url "{sdist["url"]}"\n'
        f'    sha256 "{sdist["digests"]["sha256"]}"\n'
        f'  end',
    ))
blocks.sort(key=lambda x: x[0])
out.write("\n\n".join(b for _, b in blocks) + "\n")
out.close()
print(f"Wrote {len(blocks)} resource blocks to {sys.argv[2]}", file=sys.stderr)
PY

# 4. Splice the resources into the formula between markers.
python3 - "$FORMULA" "$WORK/resources.rb" <<'PY'
import re, sys
formula_path, resources_path = sys.argv[1], sys.argv[2]
with open(formula_path) as f:
    formula = f.read()
with open(resources_path) as f:
    resources = f.read().rstrip() + "\n"

# Replace from the "# Python dependencies" header to the line before "def install".
pattern = re.compile(
    r"(  # Python dependencies[^\n]*\n(?:  #[^\n]*\n)*\n).*?(?=  def install)",
    re.DOTALL,
)
match = pattern.search(formula)
if not match:
    raise SystemExit("Could not find resources marker in formula. Header must "
                     "start with '  # Python dependencies' and be followed by "
                     "an empty line, then resource blocks, then 'def install'.")
new_formula = formula[:match.end(1)] + resources + "\n" + formula[match.end():]
with open(formula_path, "w") as f:
    f.write(new_formula)
print(f"Updated {formula_path}", file=sys.stderr)
PY

echo "Done. Review the diff and commit:"
echo "  git diff $FORMULA"
