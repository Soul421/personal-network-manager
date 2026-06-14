---
name: personal-network-manager
description: "管理个人关系网络并发现双向合作机会。用户介绍一个人、提到新认识的人、提供人物访谈或公司资料、询问谁值得合作、希望撮合两个人、核验人物背景、管理人脉或同步飞书时使用。自动提取人物、资源、需求和关系状态，区分正式人脉与候选线索，谨慎调查公开背景并提示冲突风险。"
license: MIT
metadata:
  lifecycle: validating
---

# Personal Network Manager

将公开 Skill 框架与使用者的私有人物数据分开。读取或写入人物资料前，先确认私有实例
路径；不要把真实人物资料写入本 Skill 目录。

## 默认流程

1. 识别人物、公司、职位、资源、需求、特点和关系线索。
2. 判断人物属于正式人脉还是候选线索。
   - 使用者采访过、见过、合作过或直接沟通过：正式人脉。
   - 尚未确认存在直接关系：候选线索。
3. 高可信别名自动合并；同名或身份歧义进入待确认清单。
4. 将明确事实、公开核验事实和 AI 推断分别保存。
5. 新人物执行基础公开背景调查；准备合作或出现风险时再做深度尽调。
6. 比较人物可提供的价值与其他人物的需求，生成双向合作建议。
7. 高匹配机会主动提醒使用者，但不要自动联系任何人。
8. 明确信息可以自动保存；敏感信息、歧义、删除和冲突覆盖需要确认。

## 数据来源

每条重要信息标记来源类型：

- `user_provided`：使用者直接提供或从私有材料提取。
- `public_verified`：来自可追溯公开来源。
- `ai_inference`：基于已有证据的谨慎推断。

公开调查优先使用官方、监管、司法、工商、公司官网和主流媒体。保留来源链接、发布日
期、查询日期和可信度。发现冲突或无法核验时，展示证据并提示风险，不对人物诚信作无
证据定性。详细规则见 [references/research-policy.md](references/research-policy.md)。

## 本地操作

运行脚本前设置私有实例路径：

```bash
export PNM_DATA_DIR="/path/to/private/personal-network-data"
python3 scripts/network_manager.py init
python3 scripts/network_manager.py scan "/path/to/materials"
python3 scripts/network_manager.py import-scan
python3 scripts/network_manager.py upsert "/path/to/reviewed-person.json"
python3 scripts/network_manager.py validate
python3 scripts/network_manager.py match
```

扫描结果只是待审阅候选，不得直接视为确认事实。数据结构见
[references/data-schema.md](references/data-schema.md)。使用者直接介绍人物时，先将提取
出的明确事实、资源、需求、特点和证据整理为人物 JSON，再用 `upsert` 写入；不要要求
使用者手工编辑档案。

## 飞书同步

每位使用者使用自己的飞书账号或工作空间创建自建应用，并通过环境变量或系统密钥存储
提供 `FEISHU_APP_ID` 和 `FEISHU_APP_SECRET`。不要要求使用者把密钥贴进对话、命令参
数、配置文件或仓库。

先执行安全的连通性检查，再同步多维表格：

```bash
python3 scripts/feishu_sync.py doctor
python3 scripts/feishu_sync.py sync --dry-run
python3 scripts/feishu_sync.py notify --open-id "<open_id>" --message "内测提醒" --dry-run
```

`sync` 按人物 ID 新增或更新，避免重复追加。真实写入或发送提醒前向使用者展示目标
Base、表格、记录数量和接收对象。详细配置见
[references/feishu-setup.md](references/feishu-setup.md)。

## 发布保护

公开发布前必须运行：

```bash
python3 scripts/privacy_scan.py .
python3 -m unittest discover -s tests -v
```

隐私扫描发现疑似密钥、真实私有档案或运行产物时，停止发布并处理阻断项。
公开文档和模板只能使用明确标注的虚构人物与虚构企业，不得为了演示方便复制真实案例。
