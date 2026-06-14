#!/usr/bin/env python3
"""Feishu OpenAPI connectivity and people-table synchronization."""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path


BASE_URL = "https://open.feishu.cn/open-apis"


def notification_config() -> dict:
    raw = os.environ.get("PNM_DATA_DIR")
    if not raw:
        return {}
    path = Path(raw).expanduser().resolve() / "sync" / "notification.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


def lark_channel_env(profile: str) -> dict[str, str]:
    home = Path(os.environ.get("LARK_CHANNEL_HOME", "~/.lark-channel")).expanduser().resolve()
    profile_dir = home / "profiles" / profile
    return {
        **os.environ,
        "LARK_CHANNEL": "1",
        "LARK_CHANNEL_HOME": str(home),
        "LARK_CHANNEL_PROFILE": profile,
        "LARK_CHANNEL_CONFIG": str(profile_dir / "lark-cli-source" / "config.json"),
        "LARKSUITE_CLI_CONFIG_DIR": str(profile_dir / "lark-cli"),
    }


def notify_via_lark_channel(receive_id_type: str, receive_id: str, message: str, profile: str, dry_run: bool) -> None:
    target_flag = "--user-id" if receive_id_type == "open_id" else "--chat-id"
    command = [
        "lark-cli",
        "im",
        "+messages-send",
        "--as",
        "bot",
        target_flag,
        receive_id,
        "--text",
        message,
    ]
    if dry_run:
        command.append("--dry-run")
    subprocess.run(command, env=lark_channel_env(profile), check=True)


def request_json(method: str, path: str, payload: dict | None = None, token: str | None = None) -> dict:
    body = json.dumps(payload).encode("utf-8") if payload is not None else None
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    request = urllib.request.Request(BASE_URL + path, data=body, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            result = json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"飞书 API 请求失败 HTTP {exc.code}: {detail}") from exc
    if result.get("code", 0) != 0:
        raise RuntimeError(f"飞书 API 返回错误：{result.get('code')} {result.get('msg')}")
    return result


def app_credentials() -> tuple[str, str]:
    # 优先从环境变量读取
    app_id = os.environ.get("FEISHU_APP_ID")
    app_secret = os.environ.get("FEISHU_APP_SECRET")
    if app_id and app_secret:
        return app_id, app_secret

    # 尝试从 lark-cli 配置读取
    try:
        result = subprocess.run(
            ["lark-cli", "config", "show"],
            capture_output=True, text=True, timeout=5
        )
        if result.returncode == 0:
            config = json.loads(result.stdout)
            app_id = config.get("appId")
            # appSecret 在 lark-cli 中被隐藏，需要从其他方式获取
            if app_id:
                # 尝试从系统钥匙串获取
                try:
                    secret_result = subprocess.run(
                        ["security", "find-generic-password",
                         "-s", "lark-cli",
                         "-a", app_id,
                         "-w"],
                        capture_output=True, text=True, timeout=5
                    )
                    if secret_result.returncode == 0:
                        app_secret = secret_result.stdout.strip()
                        return app_id, app_secret
                except Exception:
                    pass
    except Exception:
        pass

    raise SystemExit("缺少飞书凭证。请设置环境变量 FEISHU_APP_ID 和 FEISHU_APP_SECRET，或确保 lark-cli 已配置。")


def tenant_token() -> str:
    app_id, app_secret = app_credentials()
    result = request_json(
        "POST",
        "/auth/v3/tenant_access_token/internal",
        {"app_id": app_id, "app_secret": app_secret},
    )
    return result["tenant_access_token"]


def command_doctor(_: argparse.Namespace) -> int:
    tenant_token()
    print("飞书自建应用凭证有效，已成功获取应用访问凭证（令牌未输出）。")
    return 0


def command_create_base(args: argparse.Namespace) -> int:
    """自动创建飞书多维表格并配置字段"""
    token = tenant_token()

    # 创建多维表格
    result = request_json(
        "POST",
        "/bitable/v1/apps",
        {"name": args.name or "人脉管理", "folder_token": args.folder or ""},
        token,
    )
    app_token = result["data"]["app"]["app_token"]
    url = result["data"]["app"]["url"]
    print(f"已创建多维表格：{url}")

    # 获取默认表格ID
    result = request_json("GET", f"/bitable/v1/apps/{app_token}/tables", token=token)
    table_id = result["data"]["items"][0]["table_id"]

    # 重命名默认表格
    request_json(
        "PATCH",
        f"/bitable/v1/apps/{app_token}/tables/{table_id}",
        {"name": "人物档案"},
        token,
    )

    # 创建字段
    fields = [
        {"field_name": "人物ID", "type": 1},  # 文本
        {"field_name": "姓名", "type": 1},
        {"field_name": "公司", "type": 1},
        {"field_name": "职位", "type": 1},
        {"field_name": "分层", "type": 3, "property": {"options": [{"name": "正式人脉"}, {"name": "候选线索"}]}},  # 单选
        {"field_name": "关系状态", "type": 3, "property": {"options": [{"name": "formal"}, {"name": "candidate"}, {"name": "unknown"}]}},
        {"field_name": "可提供价值", "type": 1},  # 多行文本
        {"field_name": "当前需求", "type": 1},
        {"field_name": "人物特点", "type": 1},
        {"field_name": "风险提示", "type": 1},
        {"field_name": "背景信息", "type": 1},
        {"field_name": "标签", "type": 1},
        {"field_name": "更新时间", "type": 1},
    ]
    for field in fields:
        try:
            request_json(
                "POST",
                f"/bitable/v1/apps/{app_token}/tables/{table_id}/fields",
                field,
                token,
            )
        except RuntimeError:
            pass  # 字段可能已存在

    # 保存配置
    raw = os.environ.get("PNM_DATA_DIR")
    if raw:
        config_path = Path(raw).expanduser().resolve() / "sync" / "feishu-config.json"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text(
            json.dumps({"app_token": app_token, "table_id": table_id, "url": url}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        print(f"配置已保存到：{config_path}")

    print(f"\nApp Token: {app_token}")
    print(f"Table ID: {table_id}")
    print(f"\n设置环境变量后即可同步：")
    print(f"  export FEISHU_BASE_APP_TOKEN={app_token}")
    print(f"  export FEISHU_PEOPLE_TABLE_ID={table_id}")
    return 0


def private_people() -> list[dict]:
    raw = os.environ.get("PNM_DATA_DIR")
    if not raw:
        raise SystemExit("缺少 PNM_DATA_DIR。")
    root = Path(raw).expanduser().resolve()
    paths = sorted((root / "people" / "formal").glob("*.json")) + sorted(
        (root / "people" / "candidates").glob("*.json")
    )
    return [json.loads(path.read_text(encoding="utf-8")) for path in paths]


def feishu_fields(person: dict) -> dict:
    # 背调状态映射
    check_status_map = {
        "pending": "待核实",
        "clean": "✅ 无风险",
        "warning": "⚠️ 有疑点",
        "risk": "🔴 有风险",
    }
    
    return {
        "人物ID": person["id"],
        "姓名": person["name"],
        "公司": person.get("company", ""),
        "职位": person.get("title", ""),
        "分层": "正式人脉" if person.get("tier") == "formal" else "候选线索",
        "关系状态": person.get("relationship_status", "unknown"),
        "可提供价值": "\n".join(person.get("offers", [])),
        "当前需求": "\n".join(person.get("needs", [])),
        "背调状态": check_status_map.get(person.get("background_check_status", "pending"), "待核实"),
        "风险提示": "\n".join(str(item) for item in person.get("risks", [])),
        "更新时间": person.get("updated_at", ""),
    }


def remote_records(token: str, app_token: str, table_id: str) -> list[dict]:
    records = []
    page_token = None
    while True:
        query = {"page_size": 500}
        if page_token:
            query["page_token"] = page_token
        result = request_json(
            "GET",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records?{urllib.parse.urlencode(query)}",
            token=token,
        )
        data = result.get("data", {})
        records.extend(data.get("items", []))
        if not data.get("has_more"):
            return records
        page_token = data.get("page_token")


def command_sync(args: argparse.Namespace) -> int:
    app_token = os.environ.get("FEISHU_BASE_APP_TOKEN")
    table_id = os.environ.get("FEISHU_PEOPLE_TABLE_ID")
    if not app_token or not table_id:
        raise SystemExit("缺少 FEISHU_BASE_APP_TOKEN 或 FEISHU_PEOPLE_TABLE_ID。")
    people = private_people()
    print(f"目标 Base App Token：{app_token[:4]}...{app_token[-4:]}")
    print(f"目标人物表：{table_id}")
    print(f"准备同步人物：{len(people)}")
    if args.dry_run:
        print("dry-run 完成：未写入飞书。")
        return 0
    token = tenant_token()
    existing = {
        record.get("fields", {}).get("人物ID"): record["record_id"]
        for record in remote_records(token, app_token, table_id)
        if record.get("fields", {}).get("人物ID")
    }
    creates = []
    updates = []
    for person in people:
        fields = feishu_fields(person)
        record_id = existing.get(person["id"])
        if record_id:
            updates.append({"record_id": record_id, "fields": fields})
        else:
            creates.append({"fields": fields})
    if creates:
        request_json(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_create",
            {"records": creates},
            token,
        )
    if updates:
        request_json(
            "POST",
            f"/bitable/v1/apps/{app_token}/tables/{table_id}/records/batch_update",
            {"records": updates},
            token,
        )
    print(f"飞书同步完成：新增 {len(creates)}，更新 {len(updates)}。")
    return 0


def command_notify(args: argparse.Namespace) -> int:
    config = notification_config()
    receive_id = args.open_id or args.chat_id or config.get("open_id") or config.get("chat_id")
    receive_id_type = "open_id" if args.open_id or (not args.chat_id and config.get("open_id")) else "chat_id"
    if not receive_id:
        raise SystemExit("缺少通知接收对象。请传入 --open-id/--chat-id，或配置 sync/notification.json。")
    via = args.via or config.get("transport", "api")
    profile = args.profile or config.get("profile", "codex")
    if args.dry_run:
        print(f"准备通过 {via} 向 {receive_id_type}={receive_id} 发送提醒：{args.message}")
    if via == "lark-channel":
        notify_via_lark_channel(receive_id_type, receive_id, args.message, profile, args.dry_run)
        if args.dry_run:
            print("dry-run 完成：未发送消息。")
        else:
            print("飞书 Codex 桥接机器人提醒已发送。")
        return 0
    if args.dry_run:
        print("dry-run 完成：未发送消息。")
        return 0
    token = tenant_token()
    request_json(
        "POST",
        f"/im/v1/messages?receive_id_type={receive_id_type}",
        {
            "receive_id": receive_id,
            "msg_type": "text",
            "content": json.dumps({"text": args.message}, ensure_ascii=False),
        },
        token,
    )
    print("飞书机器人提醒已发送。")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor", help="验证飞书自建应用凭证").set_defaults(func=command_doctor)

    create_base = sub.add_parser("create-base", help="自动创建飞书多维表格")
    create_base.add_argument("--name", help="表格名称，默认'人脉管理'")
    create_base.add_argument("--folder", help="目标文件夹 token（可选）")
    create_base.set_defaults(func=command_create_base)

    sync = sub.add_parser("sync", help="同步人物到已配置的多维表格")
    sync.add_argument("--dry-run", action="store_true")
    sync.set_defaults(func=command_sync)

    notify = sub.add_parser("notify", help="通过飞书机器人发送人脉提醒")
    target = notify.add_mutually_exclusive_group()
    target.add_argument("--open-id", help="接收人的 open_id")
    target.add_argument("--chat-id", help="接收群聊的 chat_id")
    notify.add_argument("--message", required=True)
    notify.add_argument("--via", choices=("api", "lark-channel"), help="通知发送通道")
    notify.add_argument("--profile", help="lark-channel profile，默认 codex")
    notify.add_argument("--dry-run", action="store_true")
    notify.set_defaults(func=command_notify)
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    try:
        raise SystemExit(args.func(args))
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        raise SystemExit(1)
