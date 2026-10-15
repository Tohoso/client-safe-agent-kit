#!/usr/bin/env bash
# A deploy that would have hit production. Run from this folder: bash examples/walkthrough.sh
set -u
L="python3 scripts/ledger.py --ledger /tmp/preflight-demo.jsonl"
rm -f /tmp/preflight-demo.jsonl
echo '{"target": {"env": "production"}}' > /tmp/preflight-deploy.json

$L search "deploy production"          # 1. recall past lessons first
ID=$($L begin --action "deploy the new schema" --kind deploy \
  --loss "production data migrated by mistake; no undo" \
  --question "the target is the staging environment" \
  --method json_equals --path /tmp/preflight-deploy.json --field target.env --expected '"staging"' \
  | python3 -c "import json,sys; print(json.load(sys.stdin)['id'])")
$L verify "$ID"; echo "verify exit=$?"   # 2. fails: target.env = 'production'
$L go "$ID";     echo "go exit=$?"       # 3. refused (exit 2)
echo '{"target": {"env": "staging"}}' > /tmp/preflight-deploy.json
$L verify "$ID" >/dev/null; echo "verify exit=$?"   # 4. passes after the fix
$L go "$ID" >/dev/null; echo "go exit=$?"           # 5. allowed: now run the real deploy
$L close "$ID" --outcome useful --note "first verify caught the production target" >/dev/null
$L stats
