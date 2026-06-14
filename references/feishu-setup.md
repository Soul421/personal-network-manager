# Feishu Setup

每位使用者使用自己的飞书账号或工作空间，在飞书开发者后台创建自建应用。平台界面可
能使用“企业自建应用”这一术语，但数据和凭证由使用者自己的空间管理。

## 凭证

只通过环境变量或系统密钥存储提供：

```bash
export FEISHU_APP_ID="..."
export FEISHU_APP_SECRET="..."
export FEISHU_BASE_APP_TOKEN="..."
export FEISHU_PEOPLE_TABLE_ID="..."
```

不要把凭证写入 `.env` 后提交，也不要通过命令参数传递 App Secret。

## 建议权限

按最小权限原则启用机器人消息和多维表格所需权限。实际权限名称以飞书开发者后台当前
提示为准。先运行 `doctor`，根据返回的权限提示补充权限。

## 验证顺序

```bash
python3 scripts/feishu_sync.py doctor
python3 scripts/feishu_sync.py sync --dry-run
python3 scripts/feishu_sync.py sync
python3 scripts/feishu_sync.py notify --open-id "<open_id>" --message "人脉机会提醒" --dry-run
python3 scripts/feishu_sync.py notify --open-id "<open_id>" --message "人脉机会提醒"
```

`doctor` 只验证应用凭证，不输出访问令牌。`sync --dry-run` 展示将要同步的目标和数量，
不会写入飞书。同步以“人物ID”为业务键，已有记录会更新，新人物才会创建。第一版同
步要求使用者先准备目标 Base 和人物表，并配置对应 token。

机器人提醒支持 `--open-id` 私聊和 `--chat-id` 群聊。发送前先用 `--dry-run` 核对接收
对象；Skill 不得自动联系人物库中的外部联系人。

如果本机已运行 `lark-channel-bridge`，可以把提醒统一发送到可双向对话的 Codex 机器
人。私有实例的 `sync/notification.json` 可保存通知入口：

```json
{
  "transport": "lark-channel",
  "profile": "codex",
  "chat_id": "oc_xxx"
}
```

之后无需重复传接收对象：

```bash
python3 scripts/feishu_sync.py notify --message "人脉机会提醒" --dry-run
python3 scripts/feishu_sync.py notify --message "人脉机会提醒"
```

Base 同步仍使用 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET` 对应的飞书应用；通知入口可以单
独使用 Codex 桥接机器人，从而让使用者只需在一个机器人里接收提醒和继续对话。
