"""tests for datalight.py -- run: python -m pytest tests -q   (or: python tests/test_datalight.py)

Full-framework compatibility: set DEF_SCRIPTS to data-expert-framework's skills/data-modeling/scripts
to also run its check_dictionary / export_all on the upgrade output (skipped otherwise)."""
import copy
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "skills" / "data-light"
sys.path.insert(0, str(SKILL / "scripts"))
import datalight as dl  # noqa: E402

SHOP = SKILL / "examples" / "shop" / "data" / "model.light.json"


def shop():
    return dl.load(SHOP)


def db_rows(db, sql):
    """open, query, close -- Windows cannot delete a temp folder while a DB file is still open"""
    con = sqlite3.connect(db)
    try:
        return con.execute(sql).fetchall()
    finally:
        con.close()


def db_script(db, sql):
    con = sqlite3.connect(db)
    try:
        con.executescript(sql)
        con.commit()
    finally:
        con.close()


def run(*args, cwd=None):
    return subprocess.run([sys.executable, str(SKILL / "scripts" / "datalight.py"), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", cwd=cwd)


class Check(unittest.TestCase):
    def test_example_ok(self):
        errs, warns = dl.check(shop())
        self.assertEqual(errs, [])

    def test_reserved_and_bad_names(self):
        m = shop()
        m["tables"][0]["name"] = "user"
        m["tables"][1]["columns"][1]["name"] = "Dish Name"
        errs, _ = dl.check(m)
        self.assertTrue(any("예약어" in e for e in errs))
        self.assertTrue(any("영문 소문자" in e for e in errs))

    def test_missing_key_and_ref(self):
        m = shop()
        dish = dl.tables(m)["dish"]
        dish["columns"] = [c for c in dish["columns"] if c["type"] != "id"]
        dl.tables(m)["orders"]["columns"][1]["ref"] = "nothing"
        errs, _ = dl.check(m)
        self.assertTrue(any("구별할 칸" in e for e in errs))
        self.assertTrue(any("'nothing'" in e for e in errs))

    def test_bad_type_and_choices(self):
        m = shop()
        c = dl.tables(m)["dish"]["columns"][1]
        c["type"] = "varchar"
        dl.tables(m)["dish"]["columns"][2]["choices"] = ["a"]
        errs, _ = dl.check(m)
        self.assertTrue(any("varchar" in e for e in errs))
        self.assertTrue(any("choices 는 text" in e for e in errs))

    def test_clear_on_required(self):
        m = shop()
        dl.tables(m)["orders"]["columns"][1]["on_delete"] = "clear"
        self.assertTrue(any("clear" in e for e in dl.check(m)[0]))

    def test_required_cycle(self):
        m = shop()
        dl.tables(m)["customer"]["columns"].append(
            {"name": "orders_id", "label": "x", "type": "ref", "ref": "orders", "required": True})
        self.assertTrue(any("순환" in e for e in dl.check(m)[0]))

    def test_sample_unknown_column(self):
        m = shop()
        dl.tables(m)["dish"]["sample"][0]["colour"] = "red"
        self.assertTrue(any("colour" in e for e in dl.check(m)[0]))


class Split(unittest.TestCase):
    def test_personal_outside_pi_then_split(self):
        m = shop()
        t = dl.tables(m)["dish"]
        t["columns"].append({"name": "chef_phone", "label": "요리사 전화", "type": "text", "personal": "phone"})
        t["sample"][0]["chef_phone"] = "010"
        self.assertTrue(any("개인정보" in e for e in dl.check(m)[0]))
        moved = dl.split(m)
        self.assertEqual(len(moved), 1)
        self.assertEqual(dl.check(m)[0], [])
        pi = dl.tables(m)["pi_dish"]
        keyc = pi["columns"][0]
        self.assertEqual((keyc["type"], keyc["ref"], keyc["key"], keyc["on_delete"]), ("ref", "dish", True, "delete"))
        self.assertEqual(pi["sample"], [{"chef_phone": "010", "dish_id": 1}])
        self.assertNotIn("chef_phone", t["sample"][0])

    def test_split_existing_pi_table_appends(self):
        m = shop()
        dl.tables(m)["customer"]["columns"].append({"name": "email", "label": "메일", "type": "text", "personal": "email"})
        dl.split(m)
        self.assertIn("email", [c["name"] for c in dl.tables(m)["pi_customer"]["columns"]])
        self.assertEqual(sum(1 for t in m["tables"] if t["name"] == "pi_customer"), 1)


class Build(unittest.TestCase):
    def test_sqlite_ddl_runs_and_order(self):
        sql = dl.ddl(shop(), "sqlite")
        self.assertLess(sql.index("CREATE TABLE customer"), sql.index("CREATE TABLE orders"))
        con = sqlite3.connect(":memory:")
        con.executescript(sql)
        names = {r[0] for r in con.execute("select name from sqlite_master where type='table'")}
        self.assertTrue({"customer", "pi_customer", "dish", "orders", "order_item"} <= names)
        con.close()

    def test_postgres_ddl_shape(self):
        sql = dl.ddl(shop(), "postgresql")
        self.assertIn("GENERATED ALWAYS AS IDENTITY", sql)
        self.assertIn("numeric(15,2)", sql)
        self.assertIn("ON DELETE CASCADE", sql)
        self.assertIn("COMMENT ON COLUMN pi_customer.full_name", sql)
        self.assertNotIn("AUTOINCREMENT", sql)

    def test_build_files(self):
        with tempfile.TemporaryDirectory() as d:
            files = dl.build(shop(), d)
            for f in ("schema.sql", "erd.md", "spec.md"):
                self.assertIn(f, files)
                self.assertTrue((Path(d) / f).stat().st_size > 0)
            erd = (Path(d) / "erd.md").read_text(encoding="utf-8")
            self.assertIn("erDiagram", erd)
            self.assertIn("customer ||--|| pi_customer", erd)
            self.assertIn("orders ||--o{ order_item", erd)

    def test_example_out_is_fresh(self):
        """examples/shop/data/out must match the model (rebuild after editing the example)"""
        with tempfile.TemporaryDirectory() as d:
            dl.build(shop(), d)
            for f in ("schema.sql", "erd.md", "spec.md"):
                self.assertEqual((Path(d) / f).read_text(encoding="utf-8"),
                                 (SHOP.parent / "out" / f).read_text(encoding="utf-8"), f)


class Try(unittest.TestCase):
    def test_example_all_rules_block(self):
        ok, lines = dl.try_sqlite(shop())
        self.assertTrue(ok, "\n".join(lines))
        self.assertTrue(any("음수 금액" in l for l in lines))
        self.assertTrue(any("삭제" in l for l in lines))

    def test_without_samples(self):
        m = shop()
        m.pop("goals")
        for t in m["tables"]:
            t.pop("sample", None)
        ok, lines = dl.try_sqlite(m)
        self.assertTrue(ok, "\n".join(lines))


class Import(unittest.TestCase):
    def _csv(self, d, enc="cp949"):
        p = Path(d) / "members.csv"
        p.write_bytes("회원명,연락처,가입일,회비,활동여부,상호\n김하나,010-1111-2222,2026-01-03,\"10,000\",Y,하나상회\n"
                      "이두리,,2026.2.5,5000,N,\n".encode(enc))
        return p

    def test_plan_inference(self):
        with tempfile.TemporaryDirectory() as d:
            plan = dl.import_plan(str(self._csv(d)), "member", "회원")
            by = {c["src"]: c for c in plan["columns"]}
            self.assertEqual(plan["rows"], 2)
            self.assertEqual(by["회원명"]["personal"], "name")
            self.assertEqual(by["연락처"]["personal"], "phone")
            self.assertIsNone(by["상호"]["personal"])
            self.assertEqual(by["가입일"]["type"], "date")
            self.assertEqual(by["회비"]["type"], "money")
            self.assertEqual(by["활동여부"]["type"], "bool")
            self.assertTrue(by["회원명"]["required"])
            self.assertFalse(by["연락처"]["required"])

    def test_apply_needs_approval_then_loads(self):
        with tempfile.TemporaryDirectory() as d:
            plan = dl.import_plan(str(self._csv(d, "utf-8-sig")), "member", "회원")
            names = {"회원명": "member_name", "연락처": "phone", "가입일": "join_date", "회비": "fee",
                     "활동여부": "active_yn", "상호": "shop_name"}
            for c in plan["columns"]:
                c["name"] = names[c["src"]]
            model, db = str(Path(d) / "data" / "model.light.json"), str(Path(d) / "app.db")
            Path(d, "data").mkdir()
            with self.assertRaises(SystemExit):
                dl.import_apply(plan, model, db, "네")          # approved false
            plan["approved"] = True
            with self.assertRaises(SystemExit):
                dl.import_apply(plan, model, db, "  ")          # empty approval
            log = dl.import_apply(plan, model, db, "네 넣어 주세요")
            self.assertEqual((log["rows"], log["personal_to"]), (2, "pi_member"))
            con = sqlite3.connect(db)
            self.assertEqual(con.execute("select fee, active_yn, join_date from member order by member_id").fetchall(),
                             [(10000, 1, "2026-01-03"), (5000, 0, "2026-02-05")])
            self.assertEqual(con.execute("select member_name from pi_member order by member_id").fetchall(),
                             [("김하나",), ("이두리",)])
            con.close()
            self.assertEqual(dl.check(dl.load(model))[0], [])
            with self.assertRaises(SystemExit):
                dl.import_apply(plan, model, db, "또")          # already has rows
            self.assertEqual(dl.import_apply(plan, model, db, "더해 주세요", append=True)["rows"], 2)
            logs = (Path(d) / "data" / "import_log.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(json.loads(logs[0])["approval"], "네 넣어 주세요")

    def test_apply_into_existing_model_with_refs(self):
        """new table added next to an existing model whose tables reference each other"""
        with tempfile.TemporaryDirectory() as d:
            model = Path(d) / "model.light.json"
            m = shop()
            dl.save(m, model)
            db = str(Path(d) / "app.db")
            con = sqlite3.connect(db)
            con.executescript(dl.ddl(m, "sqlite"))
            con.close()
            p = Path(d) / "notice.csv"
            p.write_text("제목,내용\n휴무,월요일 휴무\n", encoding="utf-8")
            plan = dl.import_plan(str(p), "notice")
            for c, n in zip(plan["columns"], ("title", "body")):
                c["name"] = n
            plan["approved"] = True
            self.assertEqual(dl.import_apply(plan, str(model), db, "네")["rows"], 1)


class Upgrade(unittest.TestCase):
    def test_structure(self):
        full = dl.upgrade(shop(), pi_schema="pi")
        t = {x["name"]: x for x in full["tables"]}
        self.assertTrue(t["pi_customer"]["is_pi"])
        fn = next(c for c in t["pi_customer"]["columns"] if c["name"] == "full_name")
        self.assertTrue(fn["pi"])
        oi = {c["name"]: c for c in t["order_item"]["columns"]}
        self.assertEqual(oi["orders_id"]["fk"]["on_delete"], "CASCADE")
        self.assertEqual(oi["dish_id"]["fk"]["on_delete"], "RESTRICT")
        self.assertTrue(t["customer"]["columns"][0]["identity"])
        doms = {d["name"] for d in full["domains"]}
        self.assertTrue({c["domain"] for x in full["tables"] for c in x["columns"]} <= doms)
        kors = [x["kor"] for x in full["terms"]]
        self.assertEqual(len(kors), len(set(kors)))
        self.assertEqual(len(full["relationships"]), 4)

    def test_refuses_invalid(self):
        m = shop()
        m["tables"][0]["columns"][0]["type"] = "serial"
        with self.assertRaises(SystemExit):
            dl.upgrade(m)

    @unittest.skipUnless(os.environ.get("DEF_SCRIPTS"), "DEF_SCRIPTS (전문판 scripts 경로) 미설정")
    def test_full_framework_accepts(self):
        sd = Path(os.environ["DEF_SCRIPTS"])
        with tempfile.TemporaryDirectory() as d:
            mj = Path(d) / "model.json"
            dl.save(dl.upgrade(shop(), pi_schema="pi"), mj)
            r = subprocess.run([sys.executable, str(sd / "check_dictionary.py"), str(mj)], capture_output=True, text=True,
                               encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("errors=0", r.stdout)
            r = subprocess.run([sys.executable, str(sd / "export_all.py"), str(mj), str(Path(d) / "out")],
                               capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            if (sd / "validate_pg.py").exists() and os.environ.get("DEF_VALIDATE_PG"):
                r = subprocess.run([sys.executable, str(sd / "validate_pg.py"), "--model", str(mj)],
                                   capture_output=True, text=True, encoding="utf-8")
                self.assertIn(r.returncode, (0, 77), r.stdout + r.stderr)


class Harness(unittest.TestCase):
    """success criteria → runnable checks → commit hook / CI → irreversible-change guard → mutation check"""

    def test_goals_pass_and_fail(self):
        ok, lines = dl.try_sqlite(shop())
        self.assertTrue(ok)
        self.assertEqual(sum("성공 기준" in l and l.startswith("OK") for l in lines), 3)
        m = shop()
        m["goals"][0]["expect"] = [["옆집", 1]]
        m["goals"][1]["expect"] = 5
        m["goals"].append({"say": "없는 칸", "sql": "SELECT nope FROM dish"})
        ok, lines = dl.try_sqlite(m)
        self.assertFalse(ok)
        self.assertEqual(sum(l.startswith("FAIL: 성공 기준") for l in lines), 3)

    def test_goal_rules(self):
        m = shop()
        m["goals"] = [{"say": "x", "sql": "DELETE FROM dish"}, {"say": "y", "sql": "SELECT 1; DROP TABLE dish"},
                      {"say": "z"}, {"say": "w", "sql": "SELECT 1", "expect": "many"}]
        errs = dl.check(m)[0]
        self.assertEqual(sum("성공 기준" in e for e in errs), 4)
        m.pop("goals")
        self.assertTrue(any("성공 기준(goals)" in w for w in dl.check(m)[1]))

    def test_not_doing_fence(self):
        m = shop()
        m["tables"].append({"name": "payment", "label": "결제", "columns": [{"name": "payment_id", "type": "id"}]})
        self.assertTrue(any("not_doing" in e for e in dl.check(m)[0]))

    def test_mutations_all_caught(self):
        res = dl.mutation_check(shop())
        self.assertEqual(len(res), 5)
        self.assertTrue(all(c for _, c in res), res)

    def test_mutation_detects_weak_probe(self):
        """if a rule exists in SQL but the model forgot to say so, try cannot see it -> device has a hole"""
        m = shop()
        base = dl.ddl(m, "sqlite")
        broken = base.replace(" CHECK (status IN ('접수', '준비', '완료', '취소'))", "")
        self.assertNotEqual(base, broken)
        self.assertFalse(dl.try_sqlite(m, broken)[0])

    def test_verify_stale_and_drift(self):
        with tempfile.TemporaryDirectory() as d:
            mp = Path(d) / "model.light.json"
            m = shop()
            dl.save(m, mp)
            dl.build(m, Path(d) / "out")
            ok, lines = dl.verify(mp)
            self.assertTrue(ok, lines)
            m["tables"][1]["label"] = "반찬류"
            dl.save(m, mp)
            ok, lines = dl.verify(mp)
            self.assertFalse(ok)
            self.assertTrue(any("build" in l for l in lines))
            dl.build(m, Path(d) / "out")
            con = sqlite3.connect(Path(d) / "app.db")
            con.executescript(dl.ddl(m, "sqlite"))
            con.execute("ALTER TABLE dish ADD COLUMN old_note TEXT")
            con.execute("INSERT INTO dish(dish_name, price, old_note) VALUES ('김치', 3000, '메모')")
            con.commit()
            con.close()
            ok, lines = dl.verify(mp)
            self.assertFalse(ok)
            self.assertTrue(any("old_note" in l and "되돌릴 수 없습니다" in l for l in lines))
            self.assertTrue(dl.verify(mp, use_db=False)[0])

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_hook_blocks_bad_commit(self):
        with tempfile.TemporaryDirectory() as d:
            env = {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
                   "GIT_COMMITTER_EMAIL": "t@t"}
            g = lambda *a: subprocess.run(["git", *a], cwd=d, capture_output=True, text=True, env=env)  # noqa: E731
            g("init", "-q")
            (Path(d) / "data").mkdir()
            mp = Path(d) / "data" / "model.light.json"
            dl.save(shop(), mp)
            done = dl.hook_install(d)
            self.assertTrue(any("pre-commit" in x for x in done))
            g("add", "-A")
            self.assertEqual(g("commit", "-qm", "ok").returncode, 0)
            m = shop()
            m["tables"][0]["name"] = "user"
            dl.save(m, mp)
            g("add", "-A")
            r = g("commit", "-qm", "bad")
            self.assertNotEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("커밋을 멈췄습니다", r.stdout + r.stderr)
            self.assertIn("data/app.db", (Path(d) / ".gitignore").read_text(encoding="utf-8"))

    def test_import_backs_up_existing_db(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "app.db"
            db_script(db, "CREATE TABLE keep_me (x INTEGER); INSERT INTO keep_me VALUES (1);")
            p = Path(d) / "notice.csv"
            p.write_text("제목\n휴무\n", encoding="utf-8")
            plan = dl.import_plan(str(p), "notice")
            plan["columns"][0]["name"] = "title"
            plan["approved"] = True
            log = dl.import_apply(plan, str(Path(d) / "model.light.json"), str(db), "네")
            self.assertTrue(log["backup"])
            self.assertEqual(db_rows(log["backup"], "select x from keep_me"), [(1,)])

    def test_upgrade_carries_goals(self):
        full = dl.upgrade(shop())
        self.assertEqual(len(full["success_goals"]), 3)
        self.assertTrue(any("결제" in a for a in full["assumptions"]))


class Cli(unittest.TestCase):
    def test_check_exit_codes(self):
        self.assertEqual(run("check", SHOP).returncode, 0)
        with tempfile.TemporaryDirectory() as d:
            m = shop()
            m["tables"][0]["name"] = "order"
            p = Path(d) / "m.json"
            dl.save(m, p)
            r = run("check", p)
            self.assertEqual(r.returncode, 1)
            self.assertIn("고칠것", r.stdout)

    def test_split_preview_does_not_write(self):
        with tempfile.TemporaryDirectory() as d:
            m = shop()
            dl.tables(m)["dish"]["columns"].append({"name": "chef_name", "label": "x", "type": "text", "personal": True})
            p = Path(d) / "m.json"
            dl.save(m, p)
            before = p.read_text(encoding="utf-8")
            self.assertIn("미리보기", run("split", p).stdout)
            self.assertEqual(before, p.read_text(encoding="utf-8"))

    def test_verify_exit_codes(self):
        self.assertEqual(run("verify", SHOP, "--mutate").returncode, 0)
        with tempfile.TemporaryDirectory() as d:
            m = shop()
            m["goals"][2]["expect"] = 9
            p = Path(d) / "m.json"
            dl.save(m, p)
            self.assertEqual(run("verify", p).returncode, 1)

    def test_try_and_upgrade(self):
        self.assertEqual(run("try", SHOP).returncode, 0)
        with tempfile.TemporaryDirectory() as d:
            r = run("upgrade", SHOP, "--out", Path(d) / "model.json")
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertEqual(json.loads((Path(d) / "model.json").read_text(encoding="utf-8"))["db"], "postgresql")


if __name__ == "__main__":
    unittest.main(verbosity=1)
