#!/usr/bin/env python3
from __future__ import annotations

import argparse
import csv
import html
import json
import re
import shutil
import sys
import time
import textwrap
import urllib.error
import urllib.parse
import urllib.request
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import datetime
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Iterable

BASE_URL = "https://atcoder.jp"
SESSION_COOKIE_NAME = "REVEL_SESSION"


class ExportError(RuntimeError):
    """Expected user-facing export failure."""


@dataclass
class Submission:
    submission_id: int
    contest_id: str
    task_display: str
    task_id: str
    task_url: str
    user: str
    language: str
    score: str
    code_size: str
    status: str
    execution_time: str
    memory: str
    submitted_at: str
    detail_url: str
    source: str = ""
    relative_seconds: int | None = None


@dataclass
class Cell:
    text_parts: list[str]
    links: list[tuple[str, str]]
    time_text: str
    time_datetime: str

    def text(self) -> str:
        return normalize_text("".join(self.text_parts))


class SubmissionListParser(HTMLParser):
    """Parse AtCoder's submissions table without third-party libraries."""

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.in_tbody = False
        self.in_row = False
        self.in_cell = False
        self.in_link = False
        self.in_time = False

        self.current_cells: list[Cell] = []
        self.current_cell: Cell | None = None
        self.current_link_href = ""
        self.current_link_text: list[str] = []
        self.rows: list[list[Cell]] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}

        if tag == "tbody":
            self.in_tbody = True
        elif tag == "tr" and self.in_tbody:
            self.in_row = True
            self.current_cells = []
        elif tag == "td" and self.in_row:
            self.in_cell = True
            self.current_cell = Cell([], [], "", "")
        elif tag == "a" and self.in_cell:
            self.in_link = True
            self.current_link_href = attrs_dict.get("href", "")
            self.current_link_text = []
        elif tag == "time" and self.in_cell and self.current_cell is not None:
            self.in_time = True
            self.current_cell.time_datetime = attrs_dict.get("datetime", "")

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self.in_link:
            if self.current_cell is not None:
                self.current_cell.links.append(
                    (
                        self.current_link_href,
                        normalize_text("".join(self.current_link_text)),
                    )
                )
            self.in_link = False
            self.current_link_href = ""
            self.current_link_text = []
        elif tag == "time" and self.in_time:
            self.in_time = False
        elif tag == "td" and self.in_cell:
            if self.current_cell is not None:
                self.current_cells.append(self.current_cell)
            self.current_cell = None
            self.in_cell = False
        elif tag == "tr" and self.in_row:
            if self.current_cells:
                self.rows.append(self.current_cells)
            self.current_cells = []
            self.in_row = False
        elif tag == "tbody":
            self.in_tbody = False

    def handle_data(self, data: str) -> None:
        if not self.in_cell or self.current_cell is None:
            return
        self.current_cell.text_parts.append(data)
        if self.in_link:
            self.current_link_text.append(data)
        if self.in_time:
            self.current_cell.time_text += data


class SourceParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.capture = False
        self.depth = 0
        self.parts: list[str] = []
        self.found = False

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        attrs_dict = {key: value or "" for key, value in attrs}
        if not self.capture and attrs_dict.get("id") == "submission-code":
            self.capture = True
            self.found = True
            self.depth = 1
        elif self.capture:
            self.depth += 1

    def handle_endtag(self, tag: str) -> None:
        if self.capture:
            self.depth -= 1
            if self.depth <= 0:
                self.capture = False

    def handle_data(self, data: str) -> None:
        if self.capture:
            self.parts.append(data)

    def get_source(self) -> str | None:
        if not self.found:
            return None
        return "".join(self.parts)


class ContestTimeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.times: list[str] = []
        self.capture_time = False
        self.current_text: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        if tag != "time":
            return
        attrs_dict = {key: value or "" for key, value in attrs}
        class_name = attrs_dict.get("class", "")
        if "fixtime" in class_name:
            value = attrs_dict.get("datetime", "")
            if value:
                self.times.append(value)
            else:
                self.capture_time = True
                self.current_text = []

    def handle_endtag(self, tag: str) -> None:
        if tag == "time" and self.capture_time:
            value = normalize_text("".join(self.current_text))
            if value:
                self.times.append(value)
            self.capture_time = False
            self.current_text = []

    def handle_data(self, data: str) -> None:
        if self.capture_time:
            self.current_text.append(data)


def normalize_text(value: str) -> str:
    return " ".join(html.unescape(value).split())


def absolute_url(path_or_url: str) -> str:
    return urllib.parse.urljoin(BASE_URL, path_or_url)


def sanitize_filename(value: str, limit: int = 120) -> str:
    forbidden = '<>:"/\\|?*'
    cleaned = "".join("_" if char in forbidden else char for char in value)
    cleaned = " ".join(cleaned.split()).strip(" .")
    return (cleaned or "unnamed")[:limit]


def language_extension(language: str) -> str:
    text = language.lower()
    rules = [
        (("c++", "g++", "clang++"), "cpp"),
        (("python", "pypy"), "py"),
        (("kotlin",), "kt"),
        (("java",), "java"),
        (("rust",), "rs"),
        (("go ", "golang"), "go"),
        (("c#",), "cs"),
        (("typescript",), "ts"),
        (("javascript", "node.js"), "js"),
        (("ruby",), "rb"),
        (("php",), "php"),
        (("pascal",), "pas"),
        (("haskell",), "hs"),
        (("scala",), "scala"),
        (("swift",), "swift"),
        (("c ", "gcc", "clang"), "c"),
        (("ocaml",), "ml"),
        (("lua",), "lua"),
        (("nim",), "nim"),
        (("dart",), "dart"),
        (("julia",), "jl"),
    ]
    for keywords, extension in rules:
        if any(keyword in text for keyword in keywords):
            return extension
    return "txt"


def parse_datetime(value: str) -> datetime | None:
    value = normalize_text(value)
    if not value:
        return None

    variants = [
        value,
        value.replace(" ", "T", 1),
    ]
    formats = [
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for candidate in variants:
        try:
            return datetime.fromisoformat(candidate)
        except ValueError:
            pass
        for fmt in formats:
            try:
                return datetime.strptime(candidate, fmt)
            except ValueError:
                pass
    return None


def format_elapsed(seconds: int | None) -> str:
    if seconds is None:
        return ""
    sign = "-" if seconds < 0 else ""
    seconds = abs(seconds)
    hours, remainder = divmod(seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{sign}{hours:02d}:{minutes:02d}:{seconds:02d}"


def extract_task_id(task_url: str, task_display: str) -> str:
    match = re.search(r"/tasks/([^/?#]+)", task_url)
    if match:
        return match.group(1)
    prefix = task_display.split(" - ", 1)[0].strip()
    return prefix or "unknown_task"


def extract_problem_label(task_display: str, task_id: str) -> str:
    prefix = task_display.split(" - ", 1)[0].strip()
    if prefix:
        return prefix
    if "_" in task_id:
        return task_id.rsplit("_", 1)[-1].upper()
    return task_id


def row_to_submission(row: list[Cell], contest_id: str) -> Submission | None:
    if len(row) < 7:
        return None

    all_links = [link for cell in row for link in cell.links]
    task_link = next(
        ((href, text) for href, text in all_links if "/tasks/" in href),
        None,
    )
    detail_link = next(
        (
            (href, text)
            for href, text in all_links
            if re.search(r"/submissions/\d+(?:$|[?#])", href)
        ),
        None,
    )
    user_link = next(
        ((href, text) for href, text in all_links if "/users/" in href),
        None,
    )

    if task_link is None or detail_link is None:
        return None

    id_match = re.search(r"/submissions/(\d+)", detail_link[0])
    if not id_match:
        return None

    submitted_at = row[0].time_datetime or row[0].time_text or row[0].text()
    task_display = task_link[1] or row[1].text()
    task_url = absolute_url(task_link[0])
    task_id = extract_task_id(task_url, task_display)

    # Current AtCoder layout:
    # 0 time, 1 task, 2 user, 3 language, 4 score, 5 code size,
    # 6 result, 7 execution time, 8 memory, 9 detail.
    def cell_text(index: int) -> str:
        return row[index].text() if index < len(row) else ""

    return Submission(
        submission_id=int(id_match.group(1)),
        contest_id=contest_id,
        task_display=task_display,
        task_id=task_id,
        task_url=task_url,
        user=(user_link[1] if user_link else cell_text(2)),
        language=cell_text(3),
        score=cell_text(4),
        code_size=cell_text(5),
        status=cell_text(6),
        execution_time=cell_text(7),
        memory=cell_text(8),
        submitted_at=submitted_at,
        detail_url=absolute_url(detail_link[0]),
    )


class AtCoderClient:
    def __init__(
        self,
        revel_session: str,
        *,
        timeout: float = 60.0,
        request_interval: float = 1.0,
    ) -> None:
        self.revel_session = revel_session.strip()
        self.timeout = timeout
        self.request_interval = request_interval
        self.last_request_at = 0.0

    def _throttle(self) -> None:
        elapsed = time.monotonic() - self.last_request_at
        remaining = self.request_interval - elapsed
        if self.last_request_at > 0 and remaining > 0:
            time.sleep(remaining)

    def get(self, url: str) -> tuple[str, str]:
        self._throttle()
        request = urllib.request.Request(
            url,
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 Chrome/150.0 Safari/537.36 "
                    "atcoder-submission-exporter/1.0"
                ),
                "Accept": "text/html,application/xhtml+xml",
                "Accept-Language": "en-US,en;q=0.9,ja;q=0.8",
                "Cookie": f"{SESSION_COOKIE_NAME}={self.revel_session}",
            },
        )

        try:
            with urllib.request.urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8", errors="replace")
                final_url = response.geturl()
        except urllib.error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="replace")
            if exc.code in (403, 429):
                raise ExportError(
                    f"AtCoder returned HTTP {exc.code}. The session may be invalid, "
                    "or automated access was temporarily blocked. Reduce request "
                    "frequency and refresh REVEL_SESSION."
                ) from exc
            raise ExportError(f"HTTP {exc.code}: {normalize_text(body)[:500]}") from exc
        except urllib.error.URLError as exc:
            raise ExportError(f"Network error: {exc}") from exc
        finally:
            self.last_request_at = time.monotonic()

        if "/login" in urllib.parse.urlparse(final_url).path:
            raise ExportError(
                "AtCoder redirected to the login page. REVEL_SESSION is missing, "
                "expired, or copied incorrectly."
            )

        lower_body = body.lower()
        if (
            "please sign in first" in lower_body
            or 'action="/login"' in lower_body
            or "name=\"username\"" in lower_body
            and "name=\"password\"" in lower_body
        ):
            raise ExportError(
                "AtCoder says the session is not signed in. Refresh REVEL_SESSION "
                "from the browser."
            )

        return body, final_url


def fetch_contest_start(
    client: AtCoderClient,
    contest_id: str,
) -> datetime | None:
    body, _ = client.get(f"{BASE_URL}/contests/{urllib.parse.quote(contest_id)}?lang=en")
    parser = ContestTimeParser()
    parser.feed(body)
    for value in parser.times:
        parsed = parse_datetime(value)
        if parsed is not None:
            return parsed
    return None


def fetch_submission_summaries(
    client: AtCoderClient,
    *,
    contest_id: str,
    handle: str,
    max_submissions: int,
    status_filters: set[str] | None = None,
) -> list[Submission]:
    submissions: list[Submission] = []
    seen_ids: set[int] = set()
    page = 1

    while True:
        query = "" if page == 1 else f"?page={page}"
        url = (
            f"{BASE_URL}/contests/{urllib.parse.quote(contest_id)}"
            f"/submissions/me{query}"
        )
        body, _ = client.get(url)
        parser = SubmissionListParser()
        parser.feed(body)

        page_items = [
            item
            for row in parser.rows
            if (item := row_to_submission(row, contest_id)) is not None
        ]
        if not page_items:
            break

        new_count = 0
        for submission in page_items:
            if submission.submission_id in seen_ids:
                continue
            seen_ids.add(submission.submission_id)
            new_count += 1

            if submission.user and submission.user.lower() != handle.lower():
                raise ExportError(
                    "The configured handle does not match the account represented "
                    f"by REVEL_SESSION: expected {handle}, page shows {submission.user}."
                )
            if status_filters is not None and submission.status not in status_filters:
                continue

            submissions.append(submission)
            if max_submissions > 0 and len(submissions) >= max_submissions:
                return submissions

        if new_count == 0:
            break
        page += 1

    return submissions


def fetch_sources(
    client: AtCoderClient,
    submissions: list[Submission],
    *,
    contest_start: datetime | None,
) -> None:
    total = len(submissions)
    for index, submission in enumerate(submissions, 1):
        print(
            f"[{index}/{total}] Fetching {submission.task_display} "
            f"submission {submission.submission_id}..."
        )
        body, _ = client.get(submission.detail_url)
        parser = SourceParser()
        parser.feed(body)
        source = parser.get_source()
        if source is None:
            raise ExportError(
                "Could not find source code on submission page "
                f"{submission.submission_id}. The session may lack permission, "
                "or AtCoder's page structure may have changed."
            )
        submission.source = source

        submitted = parse_datetime(submission.submitted_at)
        if contest_start is not None and submitted is not None:
            try:
                submission.relative_seconds = int(
                    (submitted - contest_start).total_seconds()
                )
            except TypeError:
                # A timezone-naive old contest page can be encountered.
                submission.relative_seconds = None


def default_output_dir(handle: str, contest_id: str) -> Path:
    return Path(
        f"atcoder_export_{sanitize_filename(handle)}_"
        f"{sanitize_filename(contest_id)}"
    )


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


def write_export(
    submissions: list[Submission],
    *,
    output_dir: Path,
    handle: str,
    contest_id: str,
) -> None:
    # Listing pages are newest-first. Store source files chronologically.
    submissions.sort(
        key=lambda item: (
            parse_datetime(item.submitted_at) or datetime.min,
            item.submission_id,
        )
    )

    sequence_by_task: dict[str, int] = defaultdict(int)
    manifest_rows: list[dict[str, Any]] = []
    metadata: list[dict[str, Any]] = []

    for submission in submissions:
        problem_label = extract_problem_label(
            submission.task_display,
            submission.task_id,
        )
        sequence_by_task[problem_label] += 1
        sequence = sequence_by_task[problem_label]

        extension = language_extension(submission.language)
        relative = format_elapsed(submission.relative_seconds)
        relative_file = relative.replace(":", "-") if relative else "unknown"
        status = sanitize_filename(submission.status or "UNKNOWN")

        task_dir = output_dir / sanitize_filename(problem_label)
        task_dir.mkdir(parents=True, exist_ok=True)

        filename = sanitize_filename(
            f"{sequence:02d}_{submission.submission_id}_{status}"
            f"_at-{relative_file}.{extension}"
        )
        source_path = task_dir / filename
        source_path.write_text(submission.source, encoding="utf-8", newline="")

        row = {
            "sequence_in_task": sequence,
            "submission_id": submission.submission_id,
            "contest_id": contest_id,
            "task_label": problem_label,
            "task_id": submission.task_id,
            "task_name": submission.task_display,
            "user": submission.user,
            "status": submission.status,
            "score": submission.score,
            "submitted_at": submission.submitted_at,
            "relative_time_seconds": (
                submission.relative_seconds
                if submission.relative_seconds is not None
                else ""
            ),
            "relative_time": relative,
            "language": submission.language,
            "code_size": submission.code_size,
            "execution_time": submission.execution_time,
            "memory": submission.memory,
            "source_file": source_path.relative_to(output_dir).as_posix(),
            "task_url": submission.task_url,
            "submission_url": submission.detail_url,
        }
        manifest_rows.append(row)

        clean = asdict(submission)
        clean.pop("source", None)
        metadata.append(clean)

    fieldnames = list(manifest_rows[0].keys())
    with (output_dir / "manifest.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as file:
        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(manifest_rows)

    (output_dir / "submissions.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    (output_dir / "README.md").write_text(
        "\n".join(
            [
                f"# AtCoder {contest_id} — {handle}",
                "",
                f"- Exported submissions: {len(submissions)}",
                "- Source files are ordered from earliest to latest per task.",
                "- `manifest.csv` contains metadata, relative time, and source paths.",
                "- `submissions.json` contains metadata without duplicated source code.",
                "",
            ]
        ),
        encoding="utf-8",
    )


def create_zip(output_dir: Path) -> Path:
    return Path(
        shutil.make_archive(
            str(output_dir),
            "zip",
            root_dir=output_dir.parent,
            base_dir=output_dir.name,
        )
    )


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=textwrap.dedent(
            """\
            Export your own AtCoder submissions and source code.

            Authentication uses a browser REVEL_SESSION cookie. The tool does not
            store or submit your AtCoder password.
            """
        ),
    )
    parser.add_argument("--handle", required=True, help="AtCoder handle.")
    parser.add_argument(
        "--contest-id",
        required=True,
        help="AtCoder contest screen name, for example abc469 or arc200.",
    )
    parser.add_argument(
        "--revel-session",
        required=True,
        help="Value of the browser cookie named REVEL_SESSION.",
    )
    parser.add_argument(
        "--max-submissions",
        type=int,
        default=0,
        help="Maximum matching submissions to export. 0 means all. Default: 0.",
    )
    parser.add_argument(
        "--status",
        action="append",
        help="Keep only this result, for example AC or WA. Repeatable.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output directory. Generated automatically when omitted.",
    )
    parser.add_argument(
        "--zip",
        action="store_true",
        dest="make_zip",
        help="Also create a ZIP archive.",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="Replace an existing output directory and ZIP.",
    )
    parser.add_argument(
        "--request-interval",
        type=float,
        default=1.0,
        help="Minimum seconds between AtCoder requests. Default: 1.0.",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=60.0,
        help="HTTP timeout in seconds. Default: 60.",
    )
    return parser


def validate_args(args: argparse.Namespace) -> None:
    if args.max_submissions < 0:
        raise ExportError("--max-submissions cannot be negative.")
    if args.request_interval < 0:
        raise ExportError("--request-interval cannot be negative.")
    if args.timeout <= 0:
        raise ExportError("--timeout must be positive.")
    if not re.fullmatch(r"[A-Za-z0-9_-]+", args.contest_id):
        raise ExportError(
            "--contest-id may contain only letters, digits, underscores, and hyphens."
        )
    if not args.revel_session.strip():
        raise ExportError("--revel-session cannot be empty.")


def run(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    validate_args(args)

    client = AtCoderClient(
        args.revel_session,
        timeout=args.timeout,
        request_interval=args.request_interval,
    )
    status_filters = set(args.status) if args.status else None

    print(
        f"Reading {args.handle}'s submissions for contest {args.contest_id}..."
    )
    contest_start = fetch_contest_start(client, args.contest_id)
    submissions = fetch_submission_summaries(
        client,
        contest_id=args.contest_id,
        handle=args.handle,
        max_submissions=args.max_submissions,
        status_filters=status_filters,
    )
    if not submissions:
        raise ExportError(
            "No matching submissions were found. Check contest ID, account, "
            "filters, and REVEL_SESSION."
        )

    print(f"Found {len(submissions)} submission(s).")
    fetch_sources(
        client,
        submissions,
        contest_start=contest_start,
    )

    output_dir = args.output or default_output_dir(
        args.handle,
        args.contest_id,
    )
    prepare_output(
        output_dir,
        overwrite=args.overwrite,
        make_zip=args.make_zip,
    )
    write_export(
        submissions,
        output_dir=output_dir,
        handle=args.handle,
        contest_id=args.contest_id,
    )

    print(f"Exported to: {output_dir.resolve()}")
    if args.make_zip:
        zip_path = create_zip(output_dir)
        print(f"ZIP archive: {zip_path.resolve()}")
    return 0
