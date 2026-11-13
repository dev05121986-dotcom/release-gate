import json
import sys

from .models import Result


def render(result: Result, as_json: bool) -> None:
    if as_json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
        return
    for item in result.checks:
        if item["status"] != "error":
            label = "PASS" if item["status"] == "passed" else "FAIL"
            print(f"{label} {item['id']}: {item['message']}")
    for error in result.errors:
        print(f"ERROR {error['code']}: {error['message']}", file=sys.stderr)
    if result.checks:
        label = {"passed": "APROVADO", "failed": "REPROVADO", "error": "ERRO"}[result.status]
        print(f"Release gate: {label}")
