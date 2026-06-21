import importlib.util
import json
import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]


def load(name, relative):
    spec = importlib.util.spec_from_file_location(name, ROOT / relative)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


network = load("network_manager", "scripts/network_manager.py")
privacy = load("privacy_scan", "scripts/privacy_scan.py")
feishu = load("feishu_sync", "scripts/feishu_sync.py")


class NetworkManagerTests(unittest.TestCase):
    def test_extracts_full_name_and_marks_candidate(self):
        items = network.extract_candidates(Path("fictional.md"), "林知远老师正在寻找适老化产品供应方。")
        self.assertEqual(items[0]["name"], "林知远")
        self.assertGreater(items[0]["confidence"], 0.8)

    def test_does_not_extract_common_phrases_as_people(self):
        text = "她从招商经理成长为董事长，后来成为董事长。师父总结了经验。"
        self.assertEqual(network.extract_candidates(Path("fictional.md"), text), [])

    def test_bidirectional_match(self):
        left_score, left_hits = network.directional_score(["社区健康渠道"], ["社区健康渠道"])
        right_score, right_hits = network.directional_score(["适老化产品"], ["适老化产品"])
        self.assertEqual(left_score, 1.0)
        self.assertEqual(right_score, 1.0)
        self.assertTrue(left_hits and right_hits)

    def test_private_data_must_be_outside_repo(self):
        previous = os.environ.get("PNM_DATA_DIR")
        os.environ["PNM_DATA_DIR"] = str(ROOT / "data")
        try:
            with self.assertRaises(SystemExit):
                network.data_dir()
        finally:
            if previous is None:
                os.environ.pop("PNM_DATA_DIR", None)
            else:
                os.environ["PNM_DATA_DIR"] = previous

    def test_privacy_scan_blocks_secret(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.txt"
            path.write_text("APP_" + "SECRET=" + "abcdefghijklmnop1234", encoding="utf-8")
            self.assertTrue(privacy.scan(Path(directory)))

    def test_privacy_scan_allows_fictional_template(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "person.example.json"
            path.write_text(json.dumps({"name": "林知远", "note": "fictional"}), encoding="utf-8")
            self.assertEqual(privacy.scan(Path(directory)), [])

    def test_privacy_scan_blocks_real_feishu_ids_and_local_paths(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.md"
            path.write_text(
                "chat=" + "oc_" + "1234567890abcdefghijklmnop\n"
                "owner=" + "ou_" + "1234567890abcdefghijklmnop\n"
                "app=" + "cli_" + "1234567890abcdef\n"
                "path=" + "/Us" + "ers/example/private.json\n",
                encoding="utf-8",
            )
            findings = privacy.scan(Path(directory))
            self.assertGreaterEqual(len(findings), 4)

    def test_feishu_fields_uses_stable_person_id(self):
        fields = feishu.feishu_fields(
            {
                "id": "person-fictional",
                "name": "林知远",
                "tier": "candidate",
                "relationship_strength": 2,
                "follow_up_at": "2026-07-14",
                "consent": {"share_scope": "private_only"},
                "next_actions": [{"due": "2026-07-14", "action": "发资料", "status": "open"}],
                "offers": ["社区健康渠道"],
                "needs": ["适老化产品"],
                "traits": [],
                "risks": [],
            }
        )
        self.assertEqual(fields["人物ID"], "person-fictional")
        self.assertEqual(fields["分层"], "📋 候选线索")
        self.assertEqual(fields["关系强度"], 2)
        self.assertEqual(fields["下次跟进"], "2026-07-14")
        self.assertEqual(fields["分享范围"], "private_only")
        self.assertIn("发资料", fields["下一步动作"])

    def test_validate_relationship_maintenance_fields(self):
        errors = network.validate_person(
            {
                "id": "person-fictional",
                "name": "林知远",
                "tier": "candidate",
                "relationship_strength": 6,
                "offers": [],
                "needs": [],
                "interactions": {},
                "next_actions": [{"status": "later"}],
                "consent": {"share_scope": "public"},
                "evidence": [{"source_type": "user_provided"}],
            },
            Path("person.json"),
        )
        self.assertTrue(any("relationship_strength" in item for item in errors))
        self.assertTrue(any("interactions" in item for item in errors))
        self.assertTrue(any("next_actions.status" in item for item in errors))
        self.assertTrue(any("consent.share_scope" in item for item in errors))

    def test_feishu_sync_updates_existing_person_id(self):
        previous = {
            "private_people": feishu.private_people,
            "tenant_token": feishu.tenant_token,
            "remote_records": feishu.remote_records,
            "request_json": feishu.request_json,
        }
        old_app_token = os.environ.get("FEISHU_BASE_APP_TOKEN")
        old_table_id = os.environ.get("FEISHU_PEOPLE_TABLE_ID")
        calls = []
        try:
            os.environ["FEISHU_BASE_APP_TOKEN"] = "app-example"
            os.environ["FEISHU_PEOPLE_TABLE_ID"] = "table-example"
            feishu.private_people = lambda: [{"id": "person-fictional", "name": "林知远", "tier": "candidate"}]
            feishu.tenant_token = lambda: "token-example"
            feishu.remote_records = lambda token, app, table: [
                {"record_id": "record-existing", "fields": {"人物ID": "person-fictional"}}
            ]
            feishu.request_json = lambda method, path, payload=None, token=None: calls.append(
                (method, path, payload, token)
            ) or {}
            feishu.command_sync(SimpleNamespace(dry_run=False))
            self.assertEqual(len(calls), 1)
            self.assertIn("batch_update", calls[0][1])
            self.assertEqual(calls[0][2]["records"][0]["record_id"], "record-existing")
        finally:
            for name, value in previous.items():
                setattr(feishu, name, value)
            if old_app_token is None:
                os.environ.pop("FEISHU_BASE_APP_TOKEN", None)
            else:
                os.environ["FEISHU_BASE_APP_TOKEN"] = old_app_token
            if old_table_id is None:
                os.environ.pop("FEISHU_PEOPLE_TABLE_ID", None)
            else:
                os.environ["FEISHU_PEOPLE_TABLE_ID"] = old_table_id

    def test_feishu_notify_uses_configured_lark_channel(self):
        previous_data_dir = os.environ.get("PNM_DATA_DIR")
        previous_run = feishu.subprocess.run
        calls = []
        with tempfile.TemporaryDirectory() as directory:
            sync = Path(directory) / "sync"
            sync.mkdir()
            (sync / "notification.json").write_text(
                json.dumps(
                    {
                        "transport": "lark-channel",
                        "profile": "codex",
                        "chat_id": "oc_example",
                    }
                ),
                encoding="utf-8",
            )
            os.environ["PNM_DATA_DIR"] = directory
            feishu.subprocess.run = lambda command, env, check: calls.append((command, env, check))
            try:
                feishu.command_notify(
                    SimpleNamespace(
                        open_id=None,
                        chat_id=None,
                        message="人脉提醒",
                        via=None,
                        profile=None,
                        dry_run=False,
                    )
                )
            finally:
                feishu.subprocess.run = previous_run
                if previous_data_dir is None:
                    os.environ.pop("PNM_DATA_DIR", None)
                else:
                    os.environ["PNM_DATA_DIR"] = previous_data_dir
        self.assertIn("--chat-id", calls[0][0])
        self.assertIn("oc_example", calls[0][0])
        self.assertEqual(calls[0][1]["LARK_CHANNEL_PROFILE"], "codex")

    def test_upsert_saves_reviewed_person_and_merges_values(self):
        previous = os.environ.get("PNM_DATA_DIR")
        with tempfile.TemporaryDirectory() as directory:
            os.environ["PNM_DATA_DIR"] = directory
            network.command_init(SimpleNamespace())
            first = Path(directory) / "first.json"
            first.write_text(
                json.dumps(
                    {
                        "name": "林知远",
                        "tier": "formal",
                        "relationship_status": "known",
                        "offers": ["社区健康渠道"],
                        "needs": [],
                        "evidence": [],
                        "risks": ["扫描提取结果尚未人工确认"],
                        "needs_confirmation": True,
                    }
                ),
                encoding="utf-8",
            )
            second = Path(directory) / "second.json"
            second.write_text(
                json.dumps(
                    {
                        "name": "林知远",
                        "tier": "formal",
                        "relationship_status": "known",
                        "offers": ["社区健康渠道"],
                        "needs": ["适老化产品"],
                        "evidence": [],
                        "needs_confirmation": False,
                    }
                ),
                encoding="utf-8",
            )
            network.command_upsert(SimpleNamespace(file=str(first)))
            network.command_upsert(SimpleNamespace(file=str(second)))
            saved = json.loads(next((Path(directory) / "people" / "formal").glob("*.json")).read_text(encoding="utf-8"))
            self.assertEqual(saved["offers"], ["社区健康渠道"])
            self.assertEqual(saved["needs"], ["适老化产品"])
            self.assertEqual(saved["risks"], [])
        if previous is None:
            os.environ.pop("PNM_DATA_DIR", None)
        else:
            os.environ["PNM_DATA_DIR"] = previous


if __name__ == "__main__":
    unittest.main()
