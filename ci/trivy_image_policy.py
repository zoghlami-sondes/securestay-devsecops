import argparse
import json
from pathlib import Path


def has_fix(vulnerability):
    return bool((vulnerability.get("FixedVersion") or "").strip())


def write_fixable_report(report, output):
    for result in report.get("Results") or []:
        if "Vulnerabilities" in result:
            result["Vulnerabilities"] = [
                item for item in (result["Vulnerabilities"] or []) if has_fix(item)
            ]
    output.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def check_gate(report, critical_policy):
    critical = 0
    high_fixable = 0
    for result in report.get("Results") or []:
        for item in result.get("Vulnerabilities") or []:
            severity = item.get("Severity")
            if severity == "CRITICAL":
                if critical_policy == "all" or (critical_policy == "fixable" and has_fix(item)):
                    critical += 1
            elif severity == "HIGH" and has_fix(item):
                high_fixable += 1

    print(f"Image CRITICAL blocking ({critical_policy}): {critical}")
    print(f"Image HIGH blocking (fixable): {high_fixable}")
    return int(bool(critical or high_fixable))


def main():
    parser = argparse.ArgumentParser()
    commands = parser.add_subparsers(dest="command", required=True)
    fixable = commands.add_parser("fixable")
    fixable.add_argument("report", type=Path)
    fixable.add_argument("output", type=Path)
    gate = commands.add_parser("gate")
    gate.add_argument("report", type=Path)
    gate.add_argument("--critical", required=True, choices=("all", "fixable", "off"))
    args = parser.parse_args()

    report = json.loads(args.report.read_text(encoding="utf-8"))
    if not isinstance(report, dict) or not isinstance(report.get("SchemaVersion"), int):
        parser.error("invalid Trivy JSON report")
    if args.command == "fixable":
        write_fixable_report(report, args.output)
        return 0
    return check_gate(report, args.critical)


if __name__ == "__main__":
    raise SystemExit(main())
