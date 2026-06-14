# Data Schema

私有实例使用 JSON 文件保存人物和合作机会。每个人物一个文件，便于审阅和追溯。

```json
{
  "id": "person-example",
  "name": "林知远（虚构人物）",
  "aliases": ["示例人物甲"],
  "tier": "candidate",
  "relationship_status": "not_connected",
  "organizations": [{"name": "示例健康服务公司（虚构）", "role": "创始人"}],
  "offers": ["社区健康服务渠道"],
  "needs": ["适老化产品供应方"],
  "traits": ["重视长期服务"],
  "evidence": [{
    "source_type": "user_provided",
    "source": "examples/fictional-interview.md",
    "summary": "本人物、企业及合作需求均为虚构示例，不对应任何真实主体。",
    "confidence": 0.8
  }],
  "risks": [],
  "updated_at": "2026-06-14T00:00:00Z"
}
```

允许的 `tier`：

- `formal`：使用者已直接认识、采访、沟通或合作。
- `candidate`：具有潜在价值，但尚未确认直接关系。

允许的事实来源：

- `user_provided`
- `public_verified`
- `ai_inference`

不得把 AI 推断改写成已核验事实。每条风险和公开核验信息应保留证据来源与查询日期。

本文及 `templates/` 中出现的所有人物、企业、资源和需求均为虚构示例，不对应任何真实
主体。公开仓库不得加入真实人物档案、访谈原文、企业合作记录或飞书运行配置。
