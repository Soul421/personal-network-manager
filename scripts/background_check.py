#!/usr/bin/env python3
"""全网背景调查模块：通过网页搜索获取公开信息，发现风险和夸大成分。"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path


def search_via_fallback(query: str) -> list[dict]:
    """通过搜索引擎获取结果（需要外部调用）"""
    # 这个函数会被 agent 调用 webfetch 替代
    return []


def analyze_risks(person: dict, company_info: str, person_info: str) -> list[dict]:
    """分析风险和夸大成分"""
    risks = []
    
    company = person.get("company", "")
    name = person.get("name", "")
    
    # 检查公司是否真实存在
    if company and not company_info:
        risks.append({
            "type": "company_not_found",
            "severity": "high",
            "message": f"未找到 {company} 的公开信息，公司可能不存在或名称有误",
        })
    
    # 检查融资信息是否一致
    stage = person.get("stage", "")
    if stage and "融资" in stage.lower() and company_info:
        # 简单检查：如果声称融资但搜索不到
        if "融资" not in company_info and "投资" not in company_info:
            risks.append({
                "type": "funding_unverified",
                "severity": "medium",
                "message": f"声称处于 {stage} 阶段，但未找到公开融资信息",
            })
    
    # 检查负面信息
    negative_keywords = ["诉讼", "纠纷", "失信", "处罚", "风险", "问题", "暴雷", "跑路"]
    for keyword in negative_keywords:
        if keyword in company_info:
            risks.append({
                "type": "negative_news",
                "severity": "medium",
                "message": f"公司信息中发现负面关键词: {keyword}",
            })
            break
    
    # 检查个人公开形象
    if person_info:
        if "教授" in person_info or "专家" in person_info or "学者" in person_info:
            pass  # 正面信息
    else:
        risks.append({
            "type": "person_low_profile",
            "severity": "low",
            "message": f"未找到 {name} 的公开社交媒体或新闻报道",
        })
    
    return risks


def generate_report(person: dict, company_info: str, person_info: str, risks: list) -> str:
    """生成背调报告"""
    report = []
    report.append(f"# 背调报告：{person.get('name', '未知')}")
    report.append(f"\n**公司**: {person.get('company', '未知')}")
    report.append(f"**职位**: {person.get('title', '未知')}")
    report.append(f"\n---\n")
    
    # 公司信息
    report.append("## 公司公开信息")
    if company_info:
        report.append(company_info[:2000])
    else:
        report.append("未找到相关公开信息")
    report.append("\n---\n")
    
    # 个人信息
    report.append("## 个人公开信息")
    if person_info:
        report.append(person_info[:2000])
    else:
        report.append("未找到相关公开信息")
    report.append("\n---\n")
    
    # 风险提示
    if risks:
        report.append("## ⚠️ 风险提示")
        for risk in risks:
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk["severity"], "⚪")
            report.append(f"- {severity_icon} [{risk['type']}] {risk['message']}")
        report.append("")
    else:
        report.append("## ✅ 未发现明显风险\n")
    
    return "\n".join(report)


def save_background_check(person: dict, company_info: str, person_info: str, risks: list) -> str:
    """保存背调结果"""
    report = generate_report(person, company_info, person_info, risks)
    
    output_dir = Path(os.environ.get("PNM_DATA_DIR", "/tmp/pnm-test2")).expanduser().resolve()
    report_path = output_dir / "background-checks" / f"{person.get('id', person.get('name', 'unknown'))}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report, encoding="utf-8")
    
    # 保存原始数据
    data_path = output_dir / "background-checks" / f"{person.get('id', person.get('name', 'unknown'))}-raw.json"
    data_path.write_text(json.dumps({
        "person": {k: v for k, v in person.items() if k != "evidence"},
        "company_info": company_info,
        "person_info": person_info,
        "risks": risks,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    
    return str(report_path)


if __name__ == "__main__":
    # 命令行入口：读取人物文件，输出 JSON 格式的搜索查询
    if len(sys.argv) < 2:
        print("用法: python3 background_check.py <person.json>", file=sys.stderr)
        sys.exit(1)
    
    person_path = Path(sys.argv[1])
    if not person_path.exists():
        print(f"文件不存在: {person_path}", file=sys.stderr)
        sys.exit(1)
    
    person = json.loads(person_path.read_text(encoding="utf-8"))
    
    # 输出搜索查询，供 agent 调用
    queries = {
        "company": f"{person.get('company', '')} 工商信息 注册资本 股东 融资",
        "person": f"{person.get('name', '')} {person.get('company', '')} LinkedIn 微博 采访",
        "risks": f"{person.get('company', '')} 风险 诉讼 纠纷 失信",
    }
    print(json.dumps(queries, ensure_ascii=False, indent=2))
