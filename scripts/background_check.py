#!/usr/bin/env python3
"""全网背景调查模块：分析搜索结果，自动判断风险状态。"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# 负面关键词库
NEGATIVE_KEYWORDS = {
    "high": ["失信", "执行人", "限制消费", "吊销", "注销", "破产", "暴雷", "跑路", "诈骗", "犯罪"],
    "medium": ["诉讼", "纠纷", "处罚", "罚款", "警告", "风险", "问题", "争议", "投诉"],
    "low": ["经营异常", "简易注销", "股权冻结"],
}

# 正面关键词库
POSITIVE_KEYWORDS = [
    "高新技术企业", "专精特新", "上市公司", "融资", "投资", "战略合作",
    "行业领先", "技术创新", "专利", "获奖", "媒体报道",
]


def analyze_company_info(company: str, search_results: list[dict]) -> dict:
    """分析公司搜索结果"""
    result = {
        "found": False,
        "risks": [],
        "positives": [],
        "summary": "",
    }
    
    if not search_results:
        result["risks"].append({
            "type": "company_not_found",
            "severity": "high",
            "message": f"未找到「{company}」的公开信息，公司可能不存在或名称有误",
        })
        return result
    
    result["found"] = True
    all_text = " ".join(r.get("snippet", "") + " " + r.get("title", "") for r in search_results)
    
    # 检查负面信息
    for severity, keywords in NEGATIVE_KEYWORDS.items():
        for keyword in keywords:
            if keyword in all_text:
                result["risks"].append({
                    "type": f"negative_{severity}",
                    "severity": severity,
                    "message": f"公司信息中发现: {keyword}",
                })
    
    # 检查正面信息
    for keyword in POSITIVE_KEYWORDS:
        if keyword in all_text:
            result["positives"].append(keyword)
    
    # 生成摘要
    if result["risks"]:
        result["summary"] = f"发现 {len(result['risks'])} 个风险点"
    elif result["positives"]:
        result["summary"] = f"公司信息正常，有 {len(result['positives'])} 项正面信息"
    else:
        result["summary"] = "公司信息存在，但未发现明显正面或负面信息"
    
    return result


def analyze_person_info(name: str, company: str, search_results: list[dict]) -> dict:
    """分析个人搜索结果"""
    result = {
        "found": False,
        "risks": [],
        "positives": [],
        "summary": "",
    }
    
    if not search_results:
        result["risks"].append({
            "type": "person_low_profile",
            "severity": "low",
            "message": f"未找到「{name}」的公开信息，可能是新入行或信息不准确",
        })
        return result
    
    result["found"] = True
    all_text = " ".join(r.get("snippet", "") + " " + r.get("title", "") for r in search_results)
    
    # 检查是否提到这个人
    name_found = name in all_text or (company and company in all_text)
    if not name_found:
        result["risks"].append({
            "type": "person_not_matched",
            "severity": "medium",
            "message": f"搜索结果中未找到与「{name}」直接相关的信息",
        })
    
    # 检查职位一致性
    # （这里可以扩展更多检查逻辑）
    
    if result["risks"]:
        result["summary"] = f"个人信息有 {len(result['risks'])} 个疑点"
    else:
        result["summary"] = "个人信息未发现明显问题"
    
    return result


def determine_status(company_result: dict, person_result: dict) -> str:
    """根据分析结果自动判断背调状态"""
    all_risks = company_result.get("risks", []) + person_result.get("risks", [])
    
    if not all_risks:
        return "无风险"
    
    # 检查是否有高风险
    has_high = any(r.get("severity") == "high" for r in all_risks)
    if has_high:
        return "有风险"
    
    # 检查是否有中等风险
    has_medium = any(r.get("severity") == "medium" for r in all_risks)
    if has_medium:
        return "有疑点"
    
    # 只有低风险
    return "无风险"


def generate_report(person: dict, company_result: dict, person_result: dict, status: str) -> str:
    """生成背调报告"""
    report = []
    report.append(f"# 背调报告：{person.get('name', '未知')}")
    report.append(f"\n**公司**: {person.get('company', '未填写')}")
    report.append(f"**职位**: {person.get('title', '未填写')}")
    report.append(f"**背调状态**: {status}")
    report.append(f"\n---\n")
    
    # 公司信息
    report.append("## 公司调查结果")
    report.append(f"- 状态: {'✅ 已找到' if company_result.get('found') else '❌ 未找到'}")
    report.append(f"- 摘要: {company_result.get('summary', '无')}")
    if company_result.get("positives"):
        report.append(f"- 正面信息: {', '.join(company_result['positives'][:5])}")
    report.append("")
    
    # 个人信息
    report.append("## 个人调查结果")
    report.append(f"- 状态: {'✅ 已找到' if person_result.get('found') else '❌ 未找到'}")
    report.append(f"- 摘要: {person_result.get('summary', '无')}")
    report.append("")
    
    # 风险提示
    all_risks = company_result.get("risks", []) + person_result.get("risks", [])
    if all_risks:
        report.append("## ⚠️ 风险提示")
        for risk in all_risks:
            severity_icon = {"high": "🔴", "medium": "🟡", "low": "🟢"}.get(risk["severity"], "⚪")
            report.append(f"- {severity_icon} {risk['message']}")
        report.append("")
    else:
        report.append("## ✅ 未发现明显风险\n")
    
    return "\n".join(report)


if __name__ == "__main__":
    # 供 agent 调用的命令行接口
    if len(sys.argv) < 2:
        print("用法: python3 background_check.py generate-queries <person.json>", file=sys.stderr)
        print("      python3 background_check.py analyze <person.json> <company_results.json> <person_results.json>", file=sys.stderr)
        sys.exit(1)
    
    command = sys.argv[1]
    
    if command == "generate-queries":
        # 生成搜索查询
        person_path = Path(sys.argv[2])
        person = json.loads(person_path.read_text(encoding="utf-8"))
        queries = {
            "company": f"{person.get('company', '')} 工商信息 注册资本 股东",
            "person": f"{person.get('name', '')} {person.get('company', '')} 采访 报道",
            "risks": f"{person.get('company', '')} 风险 诉讼 纠纷 失信",
        }
        print(json.dumps(queries, ensure_ascii=False, indent=2))
    
    elif command == "analyze":
        # 分析搜索结果并判断状态
        person_path = Path(sys.argv[2])
        company_results_path = Path(sys.argv[3])
        person_results_path = Path(sys.argv[4])
        
        person = json.loads(person_path.read_text(encoding="utf-8"))
        company_results = json.loads(company_results_path.read_text(encoding="utf-8"))
        person_results = json.loads(person_results_path.read_text(encoding="utf-8"))
        
        company_result = analyze_company_info(person.get("company", ""), company_results)
        person_result = analyze_person_info(person.get("name", ""), person.get("company", ""), person_results)
        status = determine_status(company_result, person_result)
        
        all_risks = company_result.get("risks", []) + person_result.get("risks", [])
        
        result = {
            "status": status,
            "risks": all_risks,
            "company_found": company_result.get("found", False),
            "person_found": person_result.get("found", False),
            "report": generate_report(person, company_result, person_result, status),
        }
        print(json.dumps(result, ensure_ascii=False, indent=2))
