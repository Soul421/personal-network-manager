#!/usr/bin/env python3
"""Local private-data operations for Personal Network Manager."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import unicodedata
import zipfile
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from xml.etree import ElementTree


SUPPORTED_SUFFIXES = {".md", ".txt", ".docx"}
EXCLUDED_PARTS = {
    ".git",
    ".codex-video-env",
    "node_modules",
    "personal-network-manager",
    "cc-switch",
    "__pycache__",
    "output",
    "frames",
}
SURNAMES = (
    "赵钱孙李周吴郑王冯陈褚卫蒋沈韩杨朱秦尤许何吕施张孔曹严华金魏陶姜"
    "戚谢邹喻柏水窦章云苏潘葛奚范彭郎鲁韦昌马苗凤花方俞任袁柳鲍史唐"
    "费廉岑薛雷贺倪汤滕殷罗毕郝邬安常乐于时傅皮卞齐康伍余元卜顾孟平"
    "黄和穆萧尹姚邵湛汪祁毛禹狄米贝明臧计伏成戴谈宋茅庞熊纪舒屈项祝"
    "董梁杜阮蓝闵席季麻强贾路娄危江童颜郭梅盛林刁钟徐邱骆高夏蔡田樊"
    "胡凌霍虞万支柯管卢莫经房裘缪干解应宗丁宣邓郁单杭洪包诸左石崔吉"
    "钮龚程嵇邢滑裴陆荣翁荀羊甄曲家封芮羿储靳汲邴糜松井段富巫乌焦巴"
    "弓牧隗山谷车侯宓蓬全郗班仰秋仲伊宫宁仇栾暴甘厉戎祖武符刘景詹束"
    "龙叶幸司韶郜黎蓟薄印宿白怀蒲邰从鄂索咸籍赖卓蔺屠蒙池乔阴郁胥能"
    "苍双闻莘党翟谭贡劳逄姬申扶堵冉宰郦雍却璩桑桂濮牛寿通边扈燕冀郏"
    "浦尚农温别庄晏柴瞿阎充慕连茹习艾鱼容向古易慎戈廖庾终暨居衡步都"
    "耿满弘匡国文寇广禄阙东欧沃利蔚越夔隆师巩厍聂晁勾敖融冷訾辛阚那"
    "简饶空曾毋沙乜养鞠须丰巢关蒯相查后荆红游竺权逯盖益桓公"
)
HONORIFICS = "董事长|创始人|总经理|老师|教授|博士|主任|院长|经理|总"
STRONG_HONORIFICS = "董事长|创始人|总经理|老师|教授|博士|主任|院长"
FULL_NAME_WITH_TITLE = re.compile(
    rf"(?<![\u4e00-\u9fff])([{SURNAMES}][\u4e00-\u9fff]{{1,2}})(?:[{SURNAMES}])?(?:{STRONG_HONORIFICS})"
)
TITLE_ONLY = re.compile(rf"(?<![\u4e00-\u9fff])([{SURNAMES}])(?:{HONORIFICS})")
STRUCTURED_PERSON = re.compile(
    rf"(?<![\u4e00-\u9fff])([{SURNAMES}][\u4e00-\u9fff]{{1,2}})[（(][^）)]{{0,40}}(?:{HONORIFICS})"
)
FILENAME_PERSON = re.compile(
    rf"^([{SURNAMES}][\u4e00-\u9fff]{{1,2}})(?:[{SURNAMES}]总|总)?"
    r"(?:人物访谈|采访|访谈|公众号文章)"
)
GENERIC_NAMES = {
    "人物访谈",
    "合作伙伴",
    "工作人员",
    "有限公司",
    "董事长",
    "创始人",
    "总经理",
    "负责人",
    "师父",
    "成片",
}
GENERIC_PREFIXES = ("从", "成为", "那", "这个", "我们", "你们", "他们", "她们", "一位", "这位")


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def data_dir() -> Path:
    raw = os.environ.get("PNM_DATA_DIR")
    if not raw:
        raise SystemExit("请先设置 PNM_DATA_DIR，且必须指向公开仓库之外的私有目录。")
    result = Path(raw).expanduser().resolve()
    repo = Path(__file__).resolve().parents[1]
    if result == repo or repo in result.parents:
        raise SystemExit("PNM_DATA_DIR 不能位于公开 Skill 仓库内。")
    return result


def write_json(path: Path, payload: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def read_json(path: Path) -> object:
    return json.loads(path.read_text(encoding="utf-8"))


def command_init(_: argparse.Namespace) -> int:
    root = data_dir()
    for relative in (
        "people/formal",
        "people/candidates",
        "evidence",
        "opportunities",
        "scan-results",
        "sync",
    ):
        (root / relative).mkdir(parents=True, exist_ok=True)
    config = root / "config.json"
    if not config.exists():
        write_json(
            config,
            {
                "instance_name": "Private personal network",
                "default_tier": "candidate",
                "matching_threshold": 0.45,
                "created_at": now_iso(),
            },
        )
    print(f"私有实例已准备：{root}")
    return 0


def docx_text(path: Path) -> str:
    with zipfile.ZipFile(path) as archive:
        xml = archive.read("word/document.xml")
    root = ElementTree.fromstring(xml)
    return "\n".join(node.text or "" for node in root.iter() if node.tag.endswith("}t"))


def file_text(path: Path) -> str:
    if path.suffix.lower() == ".docx":
        return docx_text(path)
    return path.read_text(encoding="utf-8", errors="ignore")


def candidate_files(source: Path, limit: int | None) -> list[Path]:
    files = []
    for path in source.rglob("*"):
        if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
            continue
        if any(part in EXCLUDED_PARTS or part.startswith(".") for part in path.parts):
            continue
        files.append(path)
    files.sort()
    return files[:limit] if limit else files


def clean_name(name: str) -> str | None:
    name = unicodedata.normalize("NFKC", name).strip()
    if (
        name in GENERIC_NAMES
        or name.startswith(GENERIC_PREFIXES)
        or len(name) < 2
        or len(name) > 4
        or name.endswith(("公司", "集团", "品牌", "医院", "研究院", "项目", "通道", "引用", "人帮"))
    ):
        return None
    return name


def context(text: str, start: int, end: int, radius: int = 75) -> str:
    return re.sub(r"\s+", " ", text[max(0, start - radius) : min(len(text), end + radius)]).strip()


def extract_candidates(path: Path, text: str) -> list[dict]:
    found: list[dict] = []
    for pattern, confidence, reason in (
        (FULL_NAME_WITH_TITLE, 0.9, "正文中出现完整姓名与职务称呼"),
        (TITLE_ONLY, 0.48, "正文中仅出现姓氏与职务称呼，需确认完整身份"),
        (STRUCTURED_PERSON, 0.86, "结构化嘉宾信息中出现姓名与职务"),
    ):
        for match in pattern.finditer(text):
            raw = match.group(1)
            name = clean_name(raw if pattern is not TITLE_ONLY else raw + "总")
            if name:
                found.append(
                    {
                        "name": name,
                        "confidence": confidence,
                        "reason": reason,
                        "snippet": context(text, match.start(), match.end()),
                    }
                )
    for match in FILENAME_PERSON.finditer(path.stem):
        name = clean_name(match.group(1))
        if name:
            found.append(
                {
                    "name": name,
                    "confidence": 0.7,
                    "reason": "文件名显示为人物访谈材料",
                    "snippet": path.name,
                }
            )
    return found


def command_scan(args: argparse.Namespace) -> int:
    root = data_dir()
    source = Path(args.source).expanduser().resolve()
    if not source.exists():
        raise SystemExit(f"扫描路径不存在：{source}")

    grouped: dict[str, dict] = {}
    errors = []
    files = candidate_files(source, args.limit)
    for path in files:
        try:
            text = file_text(path)
        except Exception as exc:  # Keep the batch reviewable when one source is malformed.
            errors.append({"source": str(path), "error": str(exc)})
            continue
        for item in extract_candidates(path, text):
            record = grouped.setdefault(
                item["name"],
                {
                    "name": item["name"],
                    "suggested_tier": "candidate",
                    "relationship_status": "unknown",
                    "needs_confirmation": True,
                    "max_confidence": 0.0,
                    "mentions": [],
                },
            )
            record["max_confidence"] = max(record["max_confidence"], item["confidence"])
            if len(record["mentions"]) < 12:
                record["mentions"].append(
                    {
                        "source_type": "user_provided",
                        "source": str(path),
                        "reason": item["reason"],
                        "snippet": item["snippet"],
                        "confidence": item["confidence"],
                    }
                )

    payload = {
        "scan_id": datetime.now().strftime("%Y%m%d-%H%M%S-%f"),
        "source_root": str(source),
        "created_at": now_iso(),
        "files_scanned": len(files),
        "candidate_count": len(grouped),
        "notice": "扫描结果仅供审阅，不代表人物身份或关系已确认。",
        "candidates": sorted(grouped.values(), key=lambda item: (-item["max_confidence"], item["name"])),
        "errors": errors,
    }
    output = root / "scan-results" / f'{payload["scan_id"]}.json'
    write_json(output, payload)
    print(f"已扫描 {len(files)} 个文件，识别 {len(grouped)} 个待审阅人物：{output}")
    return 0


def person_id(name: str) -> str:
    digest = hashlib.sha256(name.encode("utf-8")).hexdigest()[:12]
    return f"person-{digest}"


def command_import_scan(args: argparse.Namespace) -> int:
    root = data_dir()
    scans = sorted((root / "scan-results").glob("*.json"))
    if not scans:
        raise SystemExit("没有可导入的扫描结果。")
    scan_path = Path(args.scan).expanduser().resolve() if args.scan else scans[-1]
    payload = read_json(scan_path)
    created = 0
    updated = 0
    for candidate in payload.get("candidates", []):
        if len(candidate["name"]) == 2 and candidate["name"].endswith("总"):
            source_set = {item.get("source") for item in candidate.get("mentions", [])}
            merge_targets = []
            for existing_path in (root / "people" / "candidates").glob("*.json"):
                existing = read_json(existing_path)
                existing_sources = {item.get("source") for item in existing.get("evidence", [])}
                if (
                    len(existing.get("name", "")) >= 2
                    and existing["name"].startswith(candidate["name"][0])
                    and source_set & existing_sources
                ):
                    merge_targets.append((existing_path, existing))
            if len(merge_targets) == 1:
                path, person = merge_targets[0]
                if candidate["name"] not in person.setdefault("aliases", []):
                    person["aliases"].append(candidate["name"])
                person.setdefault("evidence", []).extend(candidate.get("mentions", []))
                person["updated_at"] = now_iso()
                write_json(path, person)
                updated += 1
                continue
        identifier = person_id(candidate["name"])
        path = root / "people" / "candidates" / f"{identifier}.json"
        if path.exists():
            person = read_json(path)
            known_sources = {(item.get("source"), item.get("snippet")) for item in person.get("evidence", [])}
            for mention in candidate.get("mentions", []):
                key = (mention.get("source"), mention.get("snippet"))
                if key not in known_sources:
                    person.setdefault("evidence", []).append(mention)
            person["updated_at"] = now_iso()
            updated += 1
        else:
            person = {
                "id": identifier,
                "name": candidate["name"],
                "aliases": [],
                "tier": "candidate",
                "relationship_status": "unknown",
                "organizations": [],
                "offers": [],
                "needs": [],
                "traits": [],
                "evidence": candidate.get("mentions", []),
                "risks": ["扫描提取结果尚未人工确认"],
                "needs_confirmation": True,
                "updated_at": now_iso(),
            }
            created += 1
        write_json(path, person)
    print(f"已导入候选库：新建 {created}，更新 {updated}。所有记录仍需人工确认。")
    return 0


def merge_unique(existing: list, incoming: list) -> list:
    result = list(existing)
    for item in incoming:
        if item not in result:
            result.append(item)
    return result


def command_upsert(args: argparse.Namespace) -> int:
    root = data_dir()
    incoming = read_json(Path(args.file).expanduser().resolve())
    if not isinstance(incoming, dict) or not incoming.get("name"):
        raise SystemExit("输入必须是包含 name 的人物 JSON 对象。")
    incoming.setdefault("id", person_id(incoming["name"]))
    incoming.setdefault("tier", "candidate")
    incoming.setdefault("relationship_status", "unknown")
    # 支持 resources 字段自动合并到 offers
    if incoming.get("resources") and not incoming.get("offers"):
        incoming["offers"] = incoming.pop("resources")
    elif incoming.get("resources"):
        incoming.setdefault("offers", [])
        incoming["offers"] = merge_unique(incoming["offers"], incoming.pop("resources"))
    for field in (
        "aliases",
        "organizations",
        "offers",
        "needs",
        "traits",
        "interactions",
        "next_actions",
        "evidence",
        "risks",
    ):
        incoming.setdefault(field, [])
    # 新增：标记背调状态（中文）
    incoming.setdefault("背景调查状态", "待核实")
    errors = validate_person(incoming, Path(args.file))
    if errors:
        raise SystemExit("\n".join(errors))

    paths = person_files(root)
    existing_path = next(
        (
            path
            for path in paths
            if (person := read_json(path)).get("id") == incoming["id"]
            or person.get("name") == incoming["name"]
            or incoming["name"] in person.get("aliases", [])
        ),
        None,
    )
    person = read_json(existing_path) if existing_path else {}
    for field in (
        "aliases",
        "organizations",
        "offers",
        "needs",
        "traits",
        "interactions",
        "next_actions",
        "evidence",
        "risks",
    ):
        person[field] = merge_unique(person.get(field, []), incoming.get(field, []))
    for field in (
        "id",
        "name",
        "tier",
        "relationship_status",
        "relationship_strength",
        "last_contacted_at",
        "follow_up_at",
        "consent",
        "company",
        "title",
        "phone",
        "wechat",
        "city",
        "notes",
    ):
        if field in incoming:
            person[field] = incoming[field]
    # 背调状态单独处理
    person["背景调查状态"] = incoming.get("背景调查状态", person.get("背景调查状态", "待核实"))
    person["needs_confirmation"] = bool(incoming.get("needs_confirmation", False))
    if not person["needs_confirmation"]:
        person["risks"] = [risk for risk in person["risks"] if risk != "扫描提取结果尚未人工确认"]
    person["updated_at"] = now_iso()

    target = root / "people" / ("formal" if person["tier"] == "formal" else "candidates") / f'{person["id"]}.json'
    if existing_path and existing_path != target:
        existing_path.unlink()
    write_json(target, person)
    print(f"已更新人物档案：{person['name']}（{person['tier']}）")
    return 0


def person_files(root: Path) -> list[Path]:
    return sorted((root / "people" / "formal").glob("*.json")) + sorted(
        (root / "people" / "candidates").glob("*.json")
    )


def validate_person(payload: dict, path: Path) -> list[str]:
    errors = []
    for field in ("id", "name", "tier", "offers", "needs", "evidence"):
        if field not in payload:
            errors.append(f"{path}: 缺少字段 {field}")
    if payload.get("tier") not in {"formal", "candidate"}:
        errors.append(f"{path}: tier 必须是 formal 或 candidate")
    for field in ("offers", "needs", "traits", "risks", "interactions", "next_actions", "evidence"):
        if field in payload and not isinstance(payload[field], list):
            errors.append(f"{path}: {field} 必须是列表")
    if "relationship_strength" in payload:
        strength = payload["relationship_strength"]
        if not isinstance(strength, int) or not 1 <= strength <= 5:
            errors.append(f"{path}: relationship_strength 必须是 1-5 的整数")
    if payload.get("consent") and not isinstance(payload["consent"], dict):
        errors.append(f"{path}: consent 必须是对象")
    share_scope = payload.get("consent", {}).get("share_scope") if isinstance(payload.get("consent"), dict) else None
    if share_scope and share_scope not in {"private_only", "review_before_share", "shareable"}:
        errors.append(f"{path}: consent.share_scope 无效")
    for action in payload.get("next_actions", []):
        if action.get("status") and action["status"] not in {"open", "done", "cancelled"}:
            errors.append(f"{path}: next_actions.status 无效")
    for evidence in payload.get("evidence", []):
        if evidence.get("source_type") not in {"user_provided", "public_verified", "ai_inference"}:
            errors.append(f"{path}: evidence.source_type 无效")
    return errors


def command_validate(_: argparse.Namespace) -> int:
    root = data_dir()
    files = person_files(root)
    errors = []
    for path in files:
        try:
            payload = read_json(path)
            errors.extend(validate_person(payload, path))
        except Exception as exc:
            errors.append(f"{path}: 无法读取 JSON：{exc}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    print(f"验证通过：{len(files)} 个人物档案")
    return 0


def terms(values: list[str]) -> set[str]:
    result = set()
    for value in values:
        normalized = re.sub(r"[\s，。；、,/]+", " ", value.lower())
        result.update(part for part in normalized.split() if len(part) >= 2)
        result.add(value.lower().strip())
    return {item for item in result if item}


# 语义相关词映射：当字面不匹配时，用这个做扩展匹配
SEMANTIC_MAP = {
    "融资": ["投资", "资本", "资金", "钱", "VC", "天使", "A轮", "B轮", "估值"],
    "投资": ["融资", "资本", "资金", "LP", "GP", "基金"],
    "技术": ["研发", "工程", "架构", "算法", "AI", "开发", "编程", "代码"],
    "AI": ["人工智能", "大模型", "LLM", "机器学习", "深度学习", "算法"],
    "市场": ["营销", "推广", "品牌", "渠道", "运营", "增长", "获客"],
    "客户": ["企业", "B端", "C端", "用户", "流量", "转化"],
    "电商": ["零售", "消费", "供应链", "直播", "带货"],
    "医疗": ["健康", "医药", "医院", "诊所", "诊断", "制药"],
    "教育": ["培训", "课程", "知识", "学习", "学校"],
    "制造业": ["工厂", "生产", "供应链", "品质", "产能"],
    "云": ["云计算", "SaaS", "PaaS", "IaaS", "服务器", "算力"],
}


def expand_terms(raw_terms: set[str]) -> set[str]:
    """对原始词做语义扩展"""
    expanded = set(raw_terms)
    for term in raw_terms:
        for key, synonyms in SEMANTIC_MAP.items():
            if term in synonyms or key in term:
                expanded.update(synonyms)
                expanded.add(key)
    return expanded


def directional_score(offers: list[str], needs: list[str]) -> tuple[float, list[str]]:
    offer_terms = terms(offers)
    need_terms = terms(needs)

    # 第一层：字面匹配
    hits = []
    for offer in offer_terms:
        for need in need_terms:
            if offer in need or need in offer:
                hits.append(f"{offer} ↔ {need}")

    # 第二层：语义扩展匹配
    if not hits:
        expanded_offers = expand_terms(offer_terms)
        expanded_needs = expand_terms(need_terms)
        for offer in expanded_offers:
            for need in expanded_needs:
                if offer in need or need in offer:
                    hits.append(f"{offer} ↔ {need} (语义)")

    denominator = max(1, min(len(offer_terms), len(need_terms)))
    return min(1.0, len(set(hits)) / denominator), sorted(set(hits))


def find_three_way_matches(people: list[dict], threshold: float) -> list[dict]:
    """寻找三方合作机会：A有X，B有Y，C需要X+Y"""
    matches = []
    for i, a in enumerate(people):
        for j, b in enumerate(people[i + 1 :], start=i + 1):
            for c in people[j + 1 :]:
                a_offers = set(a.get("offers", []))
                b_offers = set(b.get("offers", []))
                c_needs = set(c.get("needs", []))

                # C 的需求能被 A+B 满足
                a_covers = terms(a_offers) & terms(c_needs)
                b_covers = terms(b_offers) & terms(c_needs)

                if a_covers and b_covers and len(a_covers | b_covers) >= 2:
                    score = min(1.0, len(a_covers | b_covers) / max(1, len(c_needs)))
                    if score >= threshold:
                        matches.append(
                            {
                                "type": "three_way",
                                "participants": [a["name"], b["name"], c["name"]],
                                "participant_ids": [a["id"], b["id"], c["id"]],
                                "a_offers": sorted(a_covers),
                                "b_offers": sorted(b_covers),
                                "c_needs": sorted(c_needs),
                                "score": round(score, 3),
                                "description": f"{a['name']}的{', '.join(sorted(a_covers))} + {b['name']}的{', '.join(sorted(b_covers))} 可满足 {c['name']}的{', '.join(sorted(c_needs))}",
                                "requires_human_review": True,
                            }
                        )
    return matches


def command_update_check(args: argparse.Namespace) -> int:
    """更新背调结果（手动指定状态）"""
    root = data_dir()
    person_id = args.person_id
    check_result = args.result  # "待核实" / "无风险" / "有疑点" / "有风险"
    risks = json.loads(args.risks) if args.risks else []
    
    # 查找人物文件
    paths = person_files(root)
    target_path = next(
        (path for path in paths if read_json(path).get("id") == person_id),
        None,
    )
    if not target_path:
        print(f"未找到人物: {person_id}", file=sys.stderr)
        return 1
    
    person = read_json(target_path)
    person["背景调查状态"] = check_result
    person["risks"] = risks
    person["updated_at"] = now_iso()
    write_json(target_path, person)
    
    print(f"已更新 {person['name']} 的背调状态: {check_result}")
    if risks:
        print(f"  风险项: {len(risks)} 个")
    return 0


def command_check(args: argparse.Namespace) -> int:
    """生成搜索查询或根据搜索结果自动判断背调状态"""
    root = data_dir()
    paths = person_files(root)
    target_path = next(
        (path for path in paths if read_json(path).get("id") == args.person_id),
        None,
    )
    if not target_path:
        print(f"未找到人物: {args.person_id}", file=sys.stderr)
        return 1
    
    person = read_json(target_path)
    
    if args.results:
        # 模式2：根据搜索结果自动判断
        company_results = json.loads(Path(args.results).read_text(encoding="utf-8")) if args.results.endswith(".json") else []
        person_results = json.loads(Path(args.person_results).read_text(encoding="utf-8")) if args.person_results and args.person_results.endswith(".json") else []
        
        # 调用分析模块
        sys.path.insert(0, str(Path(__file__).parent))
        from background_check import analyze_company_info, analyze_person_info, determine_status, generate_report
        
        company_result = analyze_company_info(person.get("company", ""), company_results)
        person_result = analyze_person_info(person.get("name", ""), person.get("company", ""), person_results)
        status = determine_status(company_result, person_result)
        all_risks = company_result.get("risks", []) + person_result.get("risks", [])
        
        # 更新人物档案
        person["背景调查状态"] = status
        person["risks"] = [r.get("message", str(r)) for r in all_risks]
        person["updated_at"] = now_iso()
        write_json(target_path, person)
        
        # 保存报告
        report = generate_report(person, company_result, person_result, status)
        report_path = root / "background-checks" / f"{person['id']}.md"
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        
        print(f"✅ {person['name']} 背调完成")
        print(f"   状态: {status}")
        print(f"   风险项: {len(all_risks)} 个")
        print(f"   报告: {report_path}")
        return 0
    else:
        # 模式1：生成搜索查询
        queries = {
            "person_id": person["id"],
            "person_name": person["name"],
            "company": person.get("company", ""),
            "title": person.get("title", ""),
            "search_queries": {
                "company": f"{person.get('company', '')} 工商信息 注册资本 股东",
                "person": f"{person.get('name', '')} {person.get('company', '')} 采访 报道",
                "risks": f"{person.get('company', '')} 风险 诉讼 纠纷 失信",
            }
        }
        print(json.dumps(queries, ensure_ascii=False, indent=2))
        return 0


def command_match(_: argparse.Namespace) -> int:
    root = data_dir()
    people = [read_json(path) for path in person_files(root)]
    config = read_json(root / "config.json")
    threshold = float(config.get("matching_threshold", 0.45))

    matches = []

    # 双向匹配
    for index, left in enumerate(people):
        for right in people[index + 1 :]:
            left_to_right, lr_hits = directional_score(left.get("offers", []), right.get("needs", []))
            right_to_left, rl_hits = directional_score(right.get("offers", []), left.get("needs", []))
            score = round((left_to_right + right_to_left) / 2, 3)
            if score >= threshold:
                matches.append(
                    {
                        "type": "two_way",
                        "left_id": left["id"],
                        "left_name": left["name"],
                        "right_id": right["id"],
                        "right_name": right["name"],
                        "score": score,
                        "left_can_help_right": lr_hits,
                        "right_can_help_left": rl_hits,
                        "description": f"{left['name']} ↔ {right['name']}",
                        "requires_human_review": True,
                    }
                )

    # 三方匹配（人数>=3时才跑）
    if len(people) >= 3:
        three_way = find_three_way_matches(people, threshold)
        matches.extend(three_way)

    payload = {"created_at": now_iso(), "threshold": threshold, "matches": sorted(matches, key=lambda x: -x["score"])}
    output = root / "opportunities" / "latest.json"
    write_json(output, payload)
    print(f"发现 {len(matches)} 组待审阅合作机会：{output}")
    return 0


def parser() -> argparse.ArgumentParser:
    result = argparse.ArgumentParser(description=__doc__)
    sub = result.add_subparsers(dest="command", required=True)
    sub.add_parser("init", help="创建仓库外私有实例").set_defaults(func=command_init)
    scan = sub.add_parser("scan", help="扫描 Markdown、TXT 和 DOCX 材料")
    scan.add_argument("source")
    scan.add_argument("--limit", type=int, help="仅扫描前 N 个文件，用于小批量内测")
    scan.set_defaults(func=command_scan)
    import_scan = sub.add_parser("import-scan", help="将扫描结果导入候选库，保留待确认标记")
    import_scan.add_argument("--scan", help="指定扫描结果 JSON；默认使用最新结果")
    import_scan.set_defaults(func=command_import_scan)
    upsert = sub.add_parser("upsert", help="新增或更新一份经过审阅的人物 JSON")
    upsert.add_argument("file")
    upsert.set_defaults(func=command_upsert)
    sub.add_parser("validate", help="验证私有人物档案").set_defaults(func=command_validate)
    
    update_check = sub.add_parser("update-check", help="手动更新背调结果")
    update_check.add_argument("person_id", help="人物ID")
    update_check.add_argument("result", choices=["待核实", "无风险", "有疑点", "有风险"], help="背调结果")
    update_check.add_argument("--risks", help="风险列表 JSON")
    update_check.set_defaults(func=command_update_check)
    
    check = sub.add_parser("check", help="生成搜索查询或根据结果自动判断背调状态")
    check.add_argument("person_id", help="人物ID")
    check.add_argument("--results", help="公司搜索结果 JSON 文件路径")
    check.add_argument("--person-results", help="个人搜索结果 JSON 文件路径")
    check.set_defaults(func=command_check)
    
    sub.add_parser("match", help="计算双向价值匹配").set_defaults(func=command_match)
    return result


if __name__ == "__main__":
    args = parser().parse_args()
    raise SystemExit(args.func(args))
