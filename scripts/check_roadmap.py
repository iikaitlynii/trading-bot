"""Check local roadmap evidence consistency; never mutate GitHub or authenticate reviews."""
import argparse
import json
import re
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
COUNTS = {1: 8, 2: 7, 3: 8, 4: 8, 5: 8, 6: 8}
ASSESSMENTS = {"unverified", "partial", "implemented_pending_review", "completed"}


def github_url(value):
    if not isinstance(value, str):
        return False
    parsed = urlparse(value)
    return parsed.scheme == "https" and parsed.netloc == "github.com" and parsed.path.startswith("/iikaitlynii/trading-bot/")


def validate(data, root=ROOT):
    errors = []
    if data.get("schema_version") != 1 or not re.fullmatch(r"[0-9a-f]{40}", data.get("audited_commit", "")):
        errors.append("invalid evidence schema or audited commit")
    tasks = data.get("tasks", [])
    expected = {f"P{phase}-{number}" for phase, count in COUNTS.items() for number in range(1, count + 1)}
    ids = [t.get("id") for t in tasks]
    if len(ids) != len(expected) or set(ids) != expected:
        errors.append("all 47 unique phase task IDs are required")
    prs = {p["number"]: p for p in data.get("prs", [])}
    names = set()
    for task in tasks:
        identity = task.get("id", "?")
        phase = task.get("phase")
        if phase not in COUNTS or not identity.startswith(f"P{phase}-"):
            errors.append(f"{identity}: invalid phase")
        name = task.get("task")
        if not isinstance(name, str) or not name.strip() or (phase, name) in names:
            errors.append(f"{identity}: missing or duplicate task")
        names.add((phase, name))
        if task.get("assessment") not in ASSESSMENTS or type(task.get("complete")) is not bool:
            errors.append(f"{identity}: invalid status")
        if task.get("complete") != (task.get("assessment") == "completed"):
            errors.append(f"{identity}: completion/status mismatch")
        if not isinstance(task.get("remaining"), str) or not task["remaining"].strip():
            errors.append(f"{identity}: scope/remaining explanation required")
        references = task.get("prs", [])
        if any(number not in prs for number in references):
            errors.append(f"{identity}: unknown PR evidence")
        for path in task.get("tests", []):
            candidate = (root / path).resolve()
            if not candidate.is_relative_to(root.resolve()) or not candidate.is_file():
                errors.append(f"{identity}: missing or unsafe test path {path}")
        if task.get("complete"):
            if not references or not task.get("tests"):
                errors.append(f"{identity}: completion requires PR and task verification")
            for number in references:
                pr = prs.get(number, {})
                if pr.get("merged") is not True or not re.fullmatch(r"[0-9a-f]{40}", pr.get("merge_sha", "")):
                    errors.append(f"{identity}: merged PR evidence required")
                if pr.get("ci_conclusion") != "success" or not github_url(pr.get("ci_url")):
                    errors.append(f"{identity}: successful CI evidence required")
            review = task.get("human_review")
            if not isinstance(review, dict) or review.get("confirmed") is not True or not review.get("login") or not github_url(review.get("url")):
                errors.append(f"{identity}: explicit human confirmation required")
    return errors


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", nargs="?", type=Path, default=ROOT / "research/roadmap_evidence.json")
    args = parser.parse_args()
    errors = validate(json.loads(args.evidence.read_text()))
    if errors:
        raise SystemExit("\n".join(errors))
    print("Roadmap evidence consistent: 47 tasks; completion still requires authentic human review.")


if __name__ == "__main__":
    main()
