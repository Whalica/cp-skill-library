#!/usr/bin/env python3
from __future__ import annotations

import configparser
import sys
from pathlib import Path

from cf_export_core import ExportError, run


CONFIG_NAME = "cf_config.ini"


def pause() -> None:
    try:
        input("\n按 Enter 键关闭窗口...")
    except (EOFError, KeyboardInterrupt):
        pass


def read_config(config_path: Path) -> tuple[str, str, str]:
    if not config_path.exists():
        raise ExportError(
            f"找不到配置文件：{config_path.name}\n"
            "请确认 cf_config.ini 与程序位于同一目录。"
        )

    parser = configparser.ConfigParser(interpolation=None)
    try:
        with config_path.open("r", encoding="utf-8-sig") as file:
            parser.read_file(file)
    except configparser.Error as exc:
        raise ExportError(f"配置文件格式错误：{exc}") from exc

    if not parser.has_section("account"):
        raise ExportError("cf_config.ini 缺少 [account] 配置段。")

    handle = parser.get("account", "handle", fallback="").strip()
    api_key = parser.get("account", "api_key", fallback="").strip()
    api_secret = parser.get("account", "api_secret", fallback="").strip()

    placeholder_values = {
        "",
        "请填写你的_API_Key",
        "请填写你的_API_Secret",
        "YOUR_API_KEY",
        "YOUR_API_SECRET",
    }
    if not handle:
        raise ExportError("cf_config.ini 中的 handle 不能为空。")
    if api_key in placeholder_values:
        raise ExportError("请先在 cf_config.ini 中填写 api_key。")
    if api_secret in placeholder_values:
        raise ExportError("请先在 cf_config.ini 中填写 api_secret。")

    return handle, api_key, api_secret


def read_positive_int(prompt: str, *, default: int | None = None) -> int:
    while True:
        suffix = f" [{default}]" if default is not None else ""
        value = input(f"{prompt}{suffix}: ").strip()
        if not value and default is not None:
            return default
        try:
            number = int(value)
        except ValueError:
            print("请输入正整数。")
            continue
        if number <= 0:
            print("请输入正整数。")
            continue
        return number


def main() -> int:
    exit_code = 0
    try:
        base_dir = Path(__file__).resolve().parent
        config_path = base_dir / CONFIG_NAME
        handle, api_key, api_secret = read_config(config_path)

        print("Codeforces 提交记录与源码导出")
        print(f"当前用户：{handle}")
        print()

        contest_id = read_positive_int("请输入场次 ID")
        count = read_positive_int("请输入要扫描的最近提交数", default=300)

        output_name = f"cf_export_{handle}_{contest_id}"
        argv = [
            "--handle",
            handle,
            "--count",
            str(count),
            "--contest-id",
            str(contest_id),
            "--participant-type",
            "CONTESTANT",
            "--output",
            str(base_dir / output_name),
            "--zip",
            "--overwrite",
            "--api-key",
            api_key,
            "--api-secret",
            api_secret,
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
