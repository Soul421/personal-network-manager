# Personal Network Manager

一个面向 AI Agent 的开源人脉管理 Skill。它帮助使用者从自然语言和材料中识别人
物，维护正式人脉与候选线索，核验公开背景，并发现能够为双方创造价值的合作机会。

当前状态：`validating`。请先在私有数据上内测，再用于重要合作判断。

## 能力

- 识别人名、别名、公司、职位和来源证据
- 区分正式人脉与候选线索
- 分开保存使用者描述、公开核验和 AI 推断
- 生成双向价值匹配和撮合建议
- 通过飞书自建应用同步多维表格
- 发布前拦截密钥、私有档案和运行产物

## 隐私设计

本仓库只保存框架、空模板和虚构测试。真实人物资料必须放在仓库外的私有实例目录。
示例中的人物、企业和合作机会均为明确虚构内容，不对应任何真实主体。

```bash
export PNM_DATA_DIR="$HOME/.personal-network-manager/data"
python3 scripts/network_manager.py init
```

## 快速开始

```bash
python3 scripts/network_manager.py init
python3 scripts/network_manager.py scan "/path/to/materials"
python3 scripts/network_manager.py import-scan
python3 scripts/network_manager.py upsert "/path/to/reviewed-person.json"
python3 scripts/network_manager.py validate
python3 scripts/network_manager.py match
```

扫描只生成待审阅候选，不会自动把材料中出现的人认定为正式人脉。

## 飞书

在飞书开发者后台创建自己的自建应用，启用机器人及多维表格权限。把 App ID 和 App
Secret 放入环境变量或系统密钥存储，然后执行：

```bash
python3 scripts/feishu_sync.py doctor
python3 scripts/feishu_sync.py sync --dry-run
python3 scripts/feishu_sync.py notify --open-id "<open_id>" --message "内测提醒" --dry-run
```

同步按稳定的“人物ID”新增或更新记录，避免重复追加。机器人提醒支持私聊或群聊；取消
`--dry-run` 前先确认接收对象。

详见 [references/feishu-setup.md](references/feishu-setup.md)。

## 发布检查

```bash
python3 scripts/privacy_scan.py .
python3 -m unittest discover -s tests -v
```

隐私扫描会阻断疑似密钥、真实飞书 ID、本机用户绝对路径、私有运行目录和私有人脉实例
路径。首次发布前建议再人工检查一次提交文件列表，确认没有访谈原文、真实人物档案或
同步运行产物。

## License

MIT
