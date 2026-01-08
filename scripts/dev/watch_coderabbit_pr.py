#!/usr/bin/env python3
"""
Watch CodeRabbit PR feedback without email.

Usage:
  python3 scripts/dev/watch_coderabbit_pr.py <owner> <repo> <pr_number> --once
  python3 scripts/dev/watch_coderabbit_pr.py <owner> <repo> <pr_number> --interval 60

Auth:
  - Optional: set GITHUB_TOKEN (or GH_TOKEN) to increase rate limits.
  - If gh CLI exists + is authenticated, we'll use `gh auth token` automatically.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any, Optional


CODERABBIT_LOGINS = {
    "coderabbitai",
    "coderabbitai[bot]",
}


@dataclass(frozen=True)
class Ctx:
    owner: str
    repo: str
    pr_number: int
    token: Optional[str]


def _get_token() -> Optional[str]:
    tok = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if tok:
        return tok
    if shutil.which("gh"):
        try:
            out = subprocess.check_output(["gh", "auth", "token"], stderr=subprocess.DEVNULL, text=True).strip()
            return out or None
        except Exception:
            return None
    return None


def _request_json(url: str, token: Optional[str]) -> Any:
    headers = {
        "Accept": "application/vnd.github+json",
        "X-GitHub-Api-Version": "2022-11-28",
        "User-Agent": "watchfuleye-coderabbit-watcher",
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=30) as resp:
        payload = resp.read().decode("utf-8")
        return json.loads(payload)


def _is_coderabbit_comment(node: dict[str, Any]) -> bool:
    user = node.get("user") or {}
    login = (user.get("login") or "").lower()
    if login in CODERABBIT_LOGINS:
        return True
    body = (node.get("body") or "") + (node.get("body_text") or "")
    return "coderabbit" in body.lower()


def _fmt_line(s: str, max_len: int = 220) -> str:
    s = " ".join(s.split())
    if len(s) <= max_len:
        return s
    return s[: max_len - 1] + "…"


def fetch_pr(ctx: Ctx) -> dict[str, Any]:
    return _request_json(f"https://api.github.com/repos/{ctx.owner}/{ctx.repo}/pulls/{ctx.pr_number}", ctx.token)


def fetch_issue_comments(ctx: Ctx) -> list[dict[str, Any]]:
    return _request_json(
        f"https://api.github.com/repos/{ctx.owner}/{ctx.repo}/issues/{ctx.pr_number}/comments?per_page=100",
        ctx.token,
    )


def fetch_review_comments(ctx: Ctx) -> list[dict[str, Any]]:
    return _request_json(
        f"https://api.github.com/repos/{ctx.owner}/{ctx.repo}/pulls/{ctx.pr_number}/comments?per_page=100",
        ctx.token,
    )


def fetch_check_runs(ctx: Ctx, head_sha: str) -> dict[str, Any]:
    return _request_json(
        f"https://api.github.com/repos/{ctx.owner}/{ctx.repo}/commits/{head_sha}/check-runs?per_page=100",
        ctx.token,
    )


def print_snapshot(ctx: Ctx) -> int:
    try:
        pr = fetch_pr(ctx)
        head_sha = pr["head"]["sha"]
        title = pr.get("title", "")
        state = pr.get("state", "")
        url = pr.get("html_url", "")
        print(f"\nPR #{ctx.pr_number}: {title}")
        print(f"- url: {url}")
        print(f"- state: {state}")
        print(f"- head: {head_sha}")

        # Check-runs (focus on CodeRabbit + CI)
        try:
            checks = fetch_check_runs(ctx, head_sha)
            runs = checks.get("check_runs") or []
            coderabbit_runs = [r for r in runs if "coderabbit" in (r.get("name") or "").lower()]
            if coderabbit_runs:
                print("\nCodeRabbit check-runs:")
                for r in sorted(coderabbit_runs, key=lambda x: x.get("started_at") or ""):
                    name = r.get("name") or "CodeRabbit"
                    conc = r.get("conclusion") or r.get("status") or "unknown"
                    details = r.get("html_url") or ""
                    print(f"- {name}: {conc} ({details})")
            else:
                print("\nCodeRabbit check-runs: none detected on this SHA")
        except Exception as e:
            print(f"\nCodeRabbit check-runs: unable to fetch ({e})")

        # Comments (issue + review)
        issue_comments = [c for c in fetch_issue_comments(ctx) if _is_coderabbit_comment(c)]
        review_comments = [c for c in fetch_review_comments(ctx) if _is_coderabbit_comment(c)]

        total = len(issue_comments) + len(review_comments)
        print(f"\nCodeRabbit comments found: {total}")

        def _print_comment(c: dict[str, Any]) -> None:
            created = c.get("created_at") or ""
            link = c.get("html_url") or c.get("url") or ""
            body = c.get("body") or ""
            print(f"- {created} {link}")
            print(f"  {_fmt_line(body)}")

        if issue_comments:
            print("\nIssue comments:")
            for c in sorted(issue_comments, key=lambda x: x.get("created_at") or ""):
                _print_comment(c)

        if review_comments:
            print("\nReview comments:")
            for c in sorted(review_comments, key=lambda x: x.get("created_at") or ""):
                _print_comment(c)

        return 0
    except urllib.error.HTTPError as e:
        print(f"ERROR: GitHub API HTTP {e.code}: {e.reason}")
        return 2
    except Exception as e:
        print(f"ERROR: {e}")
        return 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("owner")
    ap.add_argument("repo")
    ap.add_argument("pr_number", type=int)
    ap.add_argument("--once", action="store_true", help="Print once and exit.")
    ap.add_argument("--interval", type=int, default=60, help="Polling interval in seconds (default: 60).")
    args = ap.parse_args()

    token = _get_token()
    if not token:
        print("NOTE: No GitHub token detected (GITHUB_TOKEN/GH_TOKEN/gh auth). Rate limits may be low.\n")

    ctx = Ctx(owner=args.owner, repo=args.repo, pr_number=args.pr_number, token=token)

    if args.once:
        return print_snapshot(ctx)

    while True:
        rc = print_snapshot(ctx)
        if rc != 0:
            return rc
        time.sleep(max(5, args.interval))


if __name__ == "__main__":
    raise SystemExit(main())


