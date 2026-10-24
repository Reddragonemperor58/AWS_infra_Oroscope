#!/usr/bin/env bash
# Quick security hygiene check. Run from the repo root.  Exit code != 0 means a finding.
set -u
fail=0
echo "1) Known-vulnerable Python dependencies (pip-audit)"
pip-audit -r services/control-plane/requirements.txt || fail=1
echo; echo "2) Secrets committed to git (tracked files only)"
if git ls-files | xargs grep -nEI '(AKIA[0-9A-Z]{16}|aws_secret_access_key|password *= *"[^"]+"|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY)' 2>/dev/null \
   | grep -v -E 'docs/|\.md:|security_audit.sh'; then fail=1; else echo "none found"; fi
echo; echo "3) Terraform vars/state tracked by git?"
if git ls-files | grep -E '\.tfvars$|\.tfstate'; then fail=1; else echo "none tracked"; fi
echo; echo "4) Raw SQL string building (injection risk)"
if grep -rnE 'text\(f"|execute\(f"|\.format\(.*(SELECT|INSERT|UPDATE|DELETE)' services/control-plane/app --include=*.py | grep -v tests/; then fail=1; else echo "none found"; fi
echo; [ $fail -eq 0 ] && echo "AUDIT CLEAN" || echo "AUDIT HAS FINDINGS"
exit $fail
