#!/usr/bin/env python3
from __future__ import annotations

import configparser
import sys
from pathlib import Path

from atcoder_export_core import ExportError, run


CONFIG_NAME = "atcoder_config.ini"


def pause() -> None:
    try:
        input("\n按 Enter 键关闭窗口...")
    except (EOFError, KeyboardInterrupt):
        pass


def read_config(path: Path) -> tuple[str, str, float]:
    if not path.exists():
        raise ExportError(
            f"找不到配置文件：{path.name}\n"
            "请确认 atcoder_config.ini 与程序位于同一目录。"
        )

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with path.open("r", encoding="utf-8-sig") as file:
            parser.read_file(file)
    except configparser.Error as exc:
        raise ExportError(f"配置文件格式错误：{exc}") from exc

    if not parser.has_section("account"):
        raise ExportError("atcoder_config.ini 缺少 [account] 配置段。")

    handle = parser.get("account", "handle", fallback="").strip()
    session = parser.get("account", "revel_session", fallback="").strip()
    interval_text = parser.get(
        "settings",
        "request_interval",
        fallback="1.0",
    ).strip()

    placeholders = {
        "",
        "请填写你的_REVEL_SESSION",
        "YOUR_REVEL_SESSION",
    }
    if not handle:
        raise ExportError("配置文件中的 handle 不能为空。")
    if session in placeholders:
        raise ExportError(
            "请先在 atcoder_config.ini 中填写 revel_session。"
        )

    try:
        interval = float(interval_text)
    except ValueError as exc:
        raise ExportError("request_interval 必须是非负数字。") from exc
    if interval < 0:
        raise ExportError("request_interval 不能为负数。")

    return handle, session, interval


def read_contest_id() -> str:
    while True:
        value = input("请输入比赛 ID（例如 abc469）: ").strip()
        if value:
            return value
        print("比赛 ID 不能为空。")


def read_limit(default: int = 200) -> int:
    while True:
        value = input(
            f"请输入最多导出的提交数 [{default}]（0 表示全部）: "
        ).strip()
        if not value:
            return default
        try:
            number = int(value)
        except ValueError:
            print("请输入非负整数。")
            continue
        if number < 0:
            print("请输入非负整数。")
            continue
        return number


def main() -> int:
    exit_code = 0
    try:
        base_dir = Path(__file__).resolve().parent
        handle, session, interval = read_config(
            base_dir / CONFIG_NAME
        )

        print("AtCoder 提交记录与源码导出")
        print(f"当前用户：{handle}")
        print()

        contest_id = read_contest_id()
        max_submissions = read_limit()
        output_dir = (
            base_dir
            / f"atcoder_export_{handle}_{contest_id}"
        )

        argv = [
            "--handle",
            handle,
            "--contest-id",
            contest_id,
            "--revel-session",
            session,
            "--max-submissions",
            str(max_submissions),
            "--request-interval",
            str(interval),
            "--output",
            str(output_dir),
            "--zip",
            "--overwrite",
        ]

        print()
        exit_code = run(argv)
    except ExportError as exc:
        print(f"\n错误：{exc}", file=sys.stderr)
        exit_code = 1
    except KeyboardInterrupt:
        print("\n已取消。", file=sys.stderr)
        exit_code = 130
    except Exception as exc:
        print(f"\n未预期错误：{exc}", file=sys.stderr)
        exit_code = 1
    finally:
        pause()

    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())
