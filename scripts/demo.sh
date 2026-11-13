#!/usr/bin/env bash
# Run after pytest succeeds and generates artifacts/junit.xml.
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
cli=$(command -v release-gate)
test -f artifacts/junit.xml
workspace=$(mktemp -d artifacts/demo.XXXXXX)
trap 'rm -rf -- "$workspace"' EXIT
cp -R examples/with-changelog examples/without-changelog "$workspace/"
for scenario in with-changelog without-changelog; do
  cp artifacts/junit.xml "$workspace/$scenario/artifacts/junit.xml"
  expected=0
  if [ "$scenario" = without-changelog ]; then expected=1; fi
  for format in text json; do
    args=()
    if [ "$format" = json ]; then args=(--json); fi
    printf '\n$ (cd %s && release-gate check' "$scenario"
    if [ "$format" = json ]; then printf ' --json'; fi
    printf ')\n'
    code=0
    (cd "$workspace/$scenario" && "$cli" check "${args[@]}") || code=$?
    printf 'exit_code=%s (esperado=%s)\n' "$code" "$expected"
    if [ "$code" -ne "$expected" ]; then
      printf 'Código inesperado na demonstração.\n' >&2
      exit 1
    fi
  done
done
