#!/usr/bin/env python3
from __future__ import annotations

import argparse
import base64
import csv
import hashlib
import json
import os
import secrets
import shutil
import sys
import time
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable

API_BASE = "https://codeforces.com/api"
API_KEY_ENV = "CF_API_KEY"
API_SECRET_ENV = "CF_API_SECRET"


class ExportError(RuntimeError):
    """Expected user-facing export failure."""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            Batch-export Codeforces submissions and source code.

            All task parameters come from command-line arguments or environment
            variables. The program never asks for handle, contest ID, count, API
            key, or API secret interactively.
            """
        ),
    )
    parser.add_argument(
        "--handle",
        required=True,
        help="Codeforces handle whose submissions will be exported.",
    )
    parser.add_argument(
        "--count",
        type=int,
        required=True,
        help="Number of recent submissions to fetch before filtering.",
    )
    parser.add_argument(
        "--from-index",
        type=int,
        default=1,
        help="1-based first submission index passed to user.status. Default: 1.",
    )
    parser.add_argument(
        "--contest-id",
        type=int,
        action="append",
        dest="contest_ids",
        help=(
            "Keep only this contest ID. Repeat for multiple contests. "
            "If omitted, export every fetched submission."
        ),
    )
    parser.add_argument(
        "--participant-type",
        action="append",
        help=(
            "Keep only this participant type, for example CONTESTANT or PRACTICE. "
            "Repeat for multiple values."
        ),
    )
    parser.add_argument(
        "--verdict",
        action="append",
        help=(
            "Keep only this verdict, for example OK or WRONG_ANSWER. "
            "Repeat for multiple values."
        ),
    )
    parser.add_argument(
        "--output",
        type=Path,
        help=(
            "Output directory. If omitted, a name is generated from handle and "
            "contest IDs."
        ),
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        dest="make_zip",
        help="Also create a ZIP archive beside the output directory.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output directory and ZIP archive.",
    )
    parser.add_argument(
        "--allow-missing-sources",
        action="store_true",
        help=(
            "Continue when the API omits some source code. Placeholder files and "
            "warnings will be produced."
        ),
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=10000,
        help="Maximum submissions requested per API call. Default: 10000.",
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=2.1,
        help=(
            "Minimum seconds between API requests when pagination is needed. "
            "Default: 2.1."
        ),
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds. Default: 60.",
    )
    parser.add_argument(
        "--api-key",
        help=f"Codeforces API key. If omitted, read environment variable {API_KEY_ENV}.",
    )
    parser.add_argument(
        "--api-secret",
        help=(
            "Codeforces API secret. Prefer environment variable "
            f"{API_SECRET_ENV} so the secret is not stored in shell history."
        ),
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.count <= 0:
        raise ExportError("--count must be positive.")
    if args.from_index <= 0:
        raise ExportError("--from-index must be positive.")
    if args.page_size <= 0:
        raise ExportError("--page-size must be positive.")
    if args.request_interval < 0:
        raise ExportError("--request-interval cannot be negative.")
    if args.timeout <= 0:
        raise ExportError("--timeout must be positive.")


def resolve_credentials(args: argparse.Namespace) -> tuple[str, str]:
    api_key = args.api_key or os.environ.get(API_KEY_ENV, "")
    api_secret = args.api_secret or os.environ.get(API_SECRET_ENV, "")
    if not api_key or not api_secret:
        raise ExportError(
            "Missing API credentials. Set CF_API_KEY and CF_API_SECRET, or pass "
            "--api-key and --api-secret."
        )
    return api_key, api_secret


def signed_api_request(
    method: str,
    params: dict[str, str],
    *,
    api_key: str,
    api_secret: str,
    timeout: float,
) -> dict[str, Any]:
    signed_params = dict(params)
    signed_params["apiKey"] = api_key
    signed_params["time"] = str(int(time.time()))

    ordered = sorted(signed_params.items(), key=lambda item: (item[0], item[1]))
    query = urllib.parse.urlencode(ordered)

    prefix = secrets.token_hex(3)
    signature_source = f"{prefix}/{method}?{query}#{api_secret}"
    signature = hashlib.sha512(signature_source.encode("utf-8")).hexdigest()
    url = f"{API_BASE}/{method}?{query}&apiSig={prefix}{signature}"

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "cf-submission-exporter/2.0",
            "Accept": "application/json",
        },
    )

    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            payload = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        raise ExportError(f"HTTP {exc.code}: {body[:1000]}") from exc
    except urllib.error.URLError as exc:
        raise ExportError(f"Network error: {exc}") from exc
    except json.JSONDecodeError as exc:
        raise ExportError("Codeforces returned a non-JSON response.") from exc

    if payload.get("status") != "OK":
        raise ExportError(str(payload.get("comment", "Unknown Codeforces API error.")))
    return payload


def fetch_submissions(
    *,
    handle: str,
    total_count: int,
    start_index: int,
    page_size: int,
    request_interval: float,
    api_key: str,
    api_secret: str,
    timeout: float,
) -> list[dict[str, Any]]:
    submissions: list[dict[str, Any]] = []
    current_index = start_index
    remaining = total_count
    first_request = True

    while remaining > 0:
        if not first_request and request_interval > 0:
            time.sleep(request_interval)
        first_request = False

        batch_size = min(page_size, remaining)
        payload = signed_api_request(
            "user.status",
            {
                "handle": handle,
                "from": str(current_index),
                "count": str(batch_size),
                "includeSources": "true",
            },
            api_key=api_key,
            api_secret=api_secret,
            timeout=timeout,
        )

        batch = payload.get("result", [])
        if not isinstance(batch, list):
            raise ExportError("Unexpected result type from Codeforces user.status.")

        submissions.extend(batch)
        received = len(batch)
        if received < batch_size:
            break

        current_index += received
        remaining -= received

    return submissions


def get_contest_id(submission: dict[str, Any]) -> int | None:
    value = submission.get("contestId")
    if isinstance(value, int):
        return value
    value = submission.get("problem", {}).get("contestId")
    return value if isinstance(value, int) else None


def get_participant_type(submission: dict[str, Any]) -> str:
    return str(submission.get("author", {}).get("participantType", ""))


def filter_submissions(
    submissions: Iterable[dict[str, Any]],
    *,
    contest_ids: set[int] | None,
    participant_types: set[str] | None,
    verdicts: set[str] | None,
) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []

    for submission in submissions:
        if contest_ids is not None and get_contest_id(submission) not in contest_ids:
            continue
        if (
            participant_types is not None
            and get_participant_type(submission) not in participant_types
        ):
            continue
        if verdicts is not None and str(submission.get("verdict", "")) not in verdicts:
            continue
        selected.append(submission)

    selected.sort(
        key=lambda item: (
            int(item.get("creationTimeSeconds", 0)),
            int(item.get("id", 0)),
        )
    )
    return selected


def decode_source(submission: dict[str, Any]) -> str | None:
    source_base64 = submission.get("sourceBase64")
    if isinstance(source_base64, str) and source_base64:
        try:
            return base64.b64decode(source_base64).decode("utf-8", errors="replace")
        except Exception as exc:
            raise ExportError(
                f"Failed to decode sourceBase64 for submission {submission.get('id')}."
            ) from exc

    for key in ("source", "sourceCode"):
        source = submission.get(key)
        if isinstance(source, str):
            return source
    return None


def sanitize_filename(value: str, limit: int = 120) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join("_" if char in forbidden else char for char in value)
    cleaned = " ".join(cleaned.split()).strip(" .")
    return (cleaned or "unnamed")[:limit]


def language_extension(language: str) -> str:
    text = language.lower()
    rules = [
        (("c++", "g++"), "cpp"),
        (("pypy", "python"), "py"),
        (("kotlin",), "kt"),
        (("java",), "java"),
        (("rust",), "rs"),
        (("golang", "go "), "go"),
        (("c#",), "cs"),
        (("typescript",), "ts"),
        (("javascript", "node.js"), "js"),
        (("ruby",), "rb"),
        (("php",), "php"),
        (("pascal",), "pas"),
        (("haskell",), "hs"),
        (("scala",), "scala"),
        (("swift",), "swift"),
        (("gnu c", "c11", "c17"), "c"),
    ]
    for keywords, extension in rules:
        if any(keyword in text for keyword in keywords):
            return extension
    return "txt"


def relative_time_display(seconds: Any) -> str:
    if not isinstance(seconds, int):
        return ""
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


def relative_time_filename(seconds: Any) -> str:
    value = relative_time_display(seconds)
    return value.replace("-", "minus-").replace(":", "-") if value else "unknown"


def verdict_label(submission: dict[str, Any]) -> str:
    verdict = str(submission.get("verdict", "UNKNOWN"))
    if verdict == "OK":
        return "AC"

    short = {
        "WRONG_ANSWER": "WA",
        "TIME_LIMIT_EXCEEDED": "TLE",
        "MEMORY_LIMIT_EXCEEDED": "MLE",
        "RUNTIME_ERROR": "RE",
        "COMPILATION_ERROR": "CE",
        "IDLENESS_LIMIT_EXCEEDED": "ILE",
        "PARTIAL": "PARTIAL",
        "SKIPPED": "SKIPPED",
        "CHALLENGED": "CHALLENGED",
    }.get(verdict, verdict)

    passed = submission.get("passedTestCount")
    if not isinstance(passed, int):
        return short

    failed_test = passed + 1
    testset = str(submission.get("testset", "")).lower()
    if testset == "pretests":
        return f"{short}_pretest-{failed_test}"
    if testset:
        return f"{short}_{sanitize_filename(testset)}-test-{failed_test}"
    return f"{short}_test-{failed_test}"


def default_output_dir(handle: str, contest_ids: list[int] | None) -> Path:
    handle_part = sanitize_filename(handle)
    if contest_ids:
        id_part = "-".join(str(value) for value in sorted(set(contest_ids)))
        return Path(f"cf_export_{handle_part}_{id_part}")
    return Path(f"cf_export_{handle_part}")


def prepare_output(output_dir: Path, *, overwrite: bool, make_zip: bool) -> None:
    zip_path = output_dir.with_suffix(".zip")

    if output_dir.exists():
        if not overwrite:
            raise ExportError(
                f"Output directory already exists: {output_dir}. Use --overwrite."
            )
        shutil.rmtree(output_dir)

    if make_zip and zip_path.exists():
        if not overwrite:
            raise ExportError(
                f"ZIP archive already exists: {zip_path}. Use --overwrite."
            )
        zip_path.unlink()

    output_dir.mkdir(parents=True)


def submission_url(submission: dict[str, Any]) -> str:
    contest_id = get_contest_id(submission)
    submission_id = submission.get("id", "")
    if contest_id is None:
        return f"https://codeforces.com/submission/{submission_id}"
    return f"https://codeforces.com/contest/{contest_id}/submission/{submission_id}"


def write_export(
    submissions: list[dict[str, Any]],
    *,
    output_dir: Path,
    handle: str,
    allow_missing_sources: bool,
) -> list[int]:
    sequence_by_problem: dict[tuple[str, str], int] = defaultdict(int)
    manifest_rows: list[dict[str, Any]] = []
    missing_source_ids: list[int] = []
    metadata_without_source: list[dict[str, Any]] = []

    for submission in submissions:
        problem = submission.get("problem", {})
        contest_id = get_contest_id(submission)
        contest_dir_name = str(contest_id) if contest_id is not None else "unknown_contest"
        problem_index = str(problem.get("index", "?"))
        problem_name = str(problem.get("name", "Unknown problem"))

        problem_key = (contest_dir_name, problem_index)
        sequence_by_problem[problem_key] += 1
        sequence = sequence_by_problem[problem_key]

        source = decode_source(submission)
        submission_id = int(submission.get("id", 0))
        if source is None:
            missing_source_ids.append(submission_id)
            if not allow_missing_sources:
                raise ExportError(
                    "The API omitted source code for submission "
                    f"{submission_id}. Confirm that the API key belongs to {handle}, "
                    "or rerun with --allow-missing-sources."
                )
            source = (
                "// Source code was not returned by the Codeforces API.\n"
                f"// Submission ID: {submission_id}\n"
            )

        language = str(submission.get("programmingLanguage", "Unknown"))
        extension = language_extension(language)
        verdict = verdict_label(submission)
        elapsed = relative_time_filename(submission.get("relativeTimeSeconds"))

        problem_dir = (
            output_dir
            / sanitize_filename(contest_dir_name)
            / sanitize_filename(problem_index)
        )
        problem_dir.mkdir(parents=True, exist_ok=True)

        source_filename = sanitize_filename(
            f"{sequence:02d}_{submission_id}_{verdict}_at-{elapsed}.{extension}"
        )
        source_path = problem_dir / source_filename
        source_path.write_text(source, encoding="utf-8", newline="")

        created_seconds = int(submission.get("creationTimeSeconds", 0))
        created_local = datetime.fromtimestamp(created_seconds).astimezone()

        manifest_rows.append(
            {
                "sequence_in_problem": sequence,
                "submission_id": submission_id,
                "contest_id": contest_id if contest_id is not None else "",
                "problem_index": problem_index,
                "problem_name": problem_name,
                "verdict": submission.get("verdict", ""),
                "verdict_detail": verdict,
                "participant_type": get_participant_type(submission),
                "relative_time_seconds": submission.get("relativeTimeSeconds", ""),
                "relative_time": relative_time_display(
                    submission.get("relativeTimeSeconds")
                ),
                "created_local": created_local.isoformat(timespec="seconds"),
                "language": language,
                "testset": submission.get("testset", ""),
                "passed_test_count": submission.get("passedTestCount", ""),
                "time_ms": submission.get("timeConsumedMillis", ""),
                "memory_bytes": submission.get("memoryConsumedBytes", ""),
                "source_file": source_path.relative_to(output_dir).as_posix(),
                "submission_url": submission_url(submission),
            }
        )

        clean_item = dict(submission)
        clean_item.pop("sourceBase64", None)
        clean_item.pop("source", None)
        clean_item.pop("sourceCode", None)
        metadata_without_source.append(clean_item)

    fieldnames = [
        "sequence_in_problem",
        "submission_id",
        "contest_id",
        "problem_index",
        "problem_name",
        "verdict",
        "verdict_detail",
        "participant_type",
        "relative_time_seconds",
        "relative_time",
        "created_local",
        "language",
        "testset",
        "passed_test_count",
        "time_ms",
        "memory_bytes",
        "source_file",
        "submission_url",
    ]

    with (output_dir / "manifest.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    (output_dir / "submissions.json").write_text(
        json.dumps(metadata_without_source, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    readme_lines = [
        f"# Codeforces submissions — {handle}",
        "",
        f"- Exported submissions: {len(submissions)}",
        "- Source files are ordered from earliest to latest inside each problem.",
        "- `manifest.csv` contains submission metadata and source paths.",
        "- `submissions.json` contains filtered raw metadata without embedded source.",
        "",
    ]
    if missing_source_ids:
        readme_lines.extend(
            [
                "## Missing source code",
                "",
                "The API omitted source code for these submission IDs:",
                "",
                ", ".join(str(value) for value in missing_source_ids),
                "",
            ]
        )

    (output_dir / "README.md").write_text(
        "\n".join(readme_lines),
        encoding="utf-8",
    )

    return missing_source_ids


def create_zip(output_dir: Path) -> Path:
    archive = shutil.make_archive(
        str(output_dir),
        "zip",
        root_dir=output_dir.parent,
        base_dir=output_dir.name,
    )
    return Path(archive)


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args)
    api_key, api_secret = resolve_credentials(args)

    output_dir = args.output or default_output_dir(args.handle, args.contest_ids)
    contest_ids = set(args.contest_ids) if args.contest_ids else None
    participant_types = (
        set(args.participant_type) if args.participant_type else None
    )
    verdicts = set(args.verdict) if args.verdict else None

    print(f"Fetching up to {args.count} submissions for {args.handle}...")
    fetched = fetch_submissions(
        handle=args.handle,
        total_count=args.count,
        start_index=args.from_index,
        page_size=args.page_size,
        request_interval=args.request_interval,
        api_key=api_key,
        api_secret=api_secret,
        timeout=args.timeout,
    )

    selected = filter_submissions(
        fetched,
        contest_ids=contest_ids,
        participant_types=participant_types,
        verdicts=verdicts,
    )
    if not selected:
        raise ExportError(
            "No submissions matched the requested filters. Increase --count or "
            "check contest ID, participant type, and verdict."
        )

    prepare_output(
        output_dir,
        overwrite=args.overwrite,
        make_zip=args.make_zip,
    )
    missing_source_ids = write_export(
        selected,
        output_dir=output_dir,
        handle=args.handle,
        allow_missing_sources=args.allow_missing_sources,
    )

    print(f"Exported {len(selected)} submissions to: {output_dir.resolve()}")
    if args.make_zip:
        zip_path = create_zip(output_dir)
        print(f"ZIP archive: {zip_path.resolve()}")
    if missing_source_ids:
        print(
            f"Warning: source code was missing for {len(missing_source_ids)} "
            "submission(s).",
            file=sys.stderr,
        )
    return 0
