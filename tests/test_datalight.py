"""tests for datalight.py -- run: python -m pytest tests -q   (or: python tests/test_datalight.py)

Full-framework compatibility: set DEF_SCRIPTS to data-expert-framework's skills/data-modeling/scripts
to also run its check_dictionary / export_all on the upgrade output (skipped otherwise)."""
import contextlib
import copy
import json
import os
import re
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


@contextlib.contextmanager
def cwd(d):
    """run inside a project folder (import plans store paths relative to it). leave before the temp dir is removed"""
    old = os.getcwd()
    os.chdir(d)
    try:
        yield
    finally:
        os.chdir(old)


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
    # PYTHONIOENCODING=cp1252 imitates a Windows (English) pipe -- the tool must still print readable Korean
    env = {**os.environ, "PYTHONIOENCODING": "cp1252"}
    return subprocess.run([sys.executable, str(SKILL / "scripts" / "datalight.py"), *map(str, args)],
                          capture_output=True, text=True, encoding="utf-8", errors="replace", cwd=cwd, env=env)


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
            for f in ("schema.sql", "erd.md", "spec.md", "book.html"):
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
            for f in ("schema.sql", "erd.md", "spec.md", "book.html"):
                self.assertEqual((Path(d) / f).read_text(encoding="utf-8"),
                                 (SHOP.parent / "out" / f).read_text(encoding="utf-8"), f)


class Works(unittest.TestCase):
    """하는 일(works) -- 누가 · 어느 화면에서 · 어느 표를 만들고·읽고·고치고·지우나. 표마다 왜 있는지가 여기서 나온다."""

    def test_example_works_cover_every_table(self):
        errs, warns = dl.check(shop())
        self.assertEqual((errs, warns), ([], []))

    def test_works_rules(self):
        m = shop()
        m["works"][0]["uses"]["nope"] = "C"
        m["works"][1]["uses"]["dish"] = "X"
        m["works"].append({"who": "누구"})
        errs, _ = dl.check(m)
        self.assertTrue(any("없는 표 'nope'" in e for e in errs), errs)
        self.assertTrue(any("C(만들기)·R(읽기)" in e for e in errs), errs)
        self.assertTrue(any("name(무슨 일인지 한 줄)" in e for e in errs), errs)
        m = shop()
        m["works"] = [w for w in m["works"] if w["name"] != "반찬 관리"]
        for w in m["works"]:
            w["uses"].pop("dish", None)
        _, warns = dl.check(m)
        self.assertTrue(any("테이블 dish: 이 표를 쓰는 일이 없습니다" in w for w in warns), warns)
        self.assertFalse(any("pi_customer" in w for w in warns))                     # 짝 표는 본 표의 일을 따른다
        m["works"] = m["works"] * 2
        _, warns = dl.check(m)
        self.assertTrue(any("7개 이하로" in w for w in warns))
        m = shop()
        del m["works"]                                                                  # 하는 일은 고르는 항목 -- 없어도 검사는 그대로
        self.assertEqual(dl.check(m), ([], []))

    def test_book_is_plain_and_escaped(self):
        h = dl.book_html(shop())
        for want in ("이 문서 읽는 법", "하는 일", "주문 받기", "주문 -- 만들기", "이 표를 쓰는 일", "누가 쓰나", "예시 (만든 값)",
                     "개인정보 짝 표", "<b>손님</b> 한 줄을 가리킵니다", "알고 싶은 것", "이번에 만들지 않을 것"):
            self.assertIn(want, h)
        m = shop()
        m["project"] = "<script>alert(1)</script>"
        m["works"][0]["say"] = "<img src=x onerror=alert(1)>"
        h = dl.book_html(m)
        self.assertNotIn("<script>alert", h)
        self.assertNotIn("<img src=x", h)
        self.assertEqual(dl.book_html(shop()), dl.book_html(shop()))                   # 시각 없음 -- 정본이 같으면 같은 파일
        del m["works"]
        self.assertIn("하는 일(works)이 적혀 있지 않습니다", dl.book_html(m))

    def test_verify_finds_stale_book(self):
        with tempfile.TemporaryDirectory() as d:
            mp = Path(d) / "data" / "model.light.json"
            mp.parent.mkdir()
            shutil.copy(SHOP, mp)
            dl.build(dl.load(mp), mp.parent / "out")
            m = dl.load(mp)
            m["works"][0]["name"] = "주문 받기 (전화)"
            dl.save(m, mp)
            self.assertIn("book.html", dl.stale_outputs(dl.load(mp), mp.parent / "out"))

    def test_upgrade_blueprint(self):
        bp = dl.upgrade_blueprint(shop())
        self.assertEqual(bp["blueprint_version"], "1")
        self.assertEqual([f["name"] for f in bp["features"]][:2], ["주문 받기", "손님 관리"])
        self.assertEqual(bp["system"]["roles"], [{"id": "role-1", "name": "사장님"}])
        scr = {s["name"]: s for s in bp["screens"]}
        self.assertEqual(scr["주문 입력"]["for"], ["role-1"])
        self.assertEqual(bp["features"][0]["screens"], [scr["주문 입력"]["id"]])
        self.assertIn("orders 만들기", bp["features"][0]["description"])
        with tempfile.TemporaryDirectory() as d:
            r = run("upgrade", SHOP, "--out", Path(d) / "model.json", "--blueprint", Path(d) / "blueprint.json")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("시스템 청사진", r.stdout)
            r = run("upgrade", SHOP, "--out", Path(d) / "m2.json", "--blueprint", Path(d) / "blueprint.json")
            self.assertEqual(r.returncode, 1)                                          # 있는 청사진은 덮지 않는다

    @unittest.skipUnless(os.environ.get("DEF_SCRIPTS"), "DEF_SCRIPTS (전문판 scripts 경로) 미설정")
    def test_full_framework_reads_the_blueprint(self):
        sd = Path(os.environ["DEF_SCRIPTS"])
        with tempfile.TemporaryDirectory() as d:
            (Path(d) / "db").mkdir()
            (Path(d) / "data").mkdir()
            dl.save(dl.upgrade(shop(), pi_schema="pi"), Path(d) / "db" / "model.json")
            dl.save(dl.upgrade_blueprint(shop()), Path(d) / "data" / "blueprint.json")
            r = subprocess.run([sys.executable, str(sd / "systembook.py"), "json", "--root", d], capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(r.returncode, 0, r.stdout[-500:] + r.stderr[-500:])
            book = json.loads(r.stdout)
            self.assertEqual(book["counts"]["features"], 5)
            self.assertFalse([p for p in book["problems"] if p["level"] == "error" and p["page"] in ("overview", "features")],
                             [p["message"] for p in book["problems"] if p["level"] == "error"])


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
        with tempfile.TemporaryDirectory() as d, cwd(d):
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
            self.assertEqual(by["회원명"]["samples"], ["(개인정보 -- 가림)"])     # real names never land in the plan
            self.assertEqual(by["상호"]["samples"][0], "하나상회")
            self.assertEqual(plan["file"], "members.csv")                    # relative, no user folder names
            self.assertFalse(by["연락처"]["required"])

    def test_apply_needs_approval_then_loads(self):
        with tempfile.TemporaryDirectory() as d, cwd(d):
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
        with tempfile.TemporaryDirectory() as d, cwd(d):
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
        self.assertEqual(len(res), 6)
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
            g = lambda *a: subprocess.run(["git", *a], cwd=d, capture_output=True, text=True, encoding="utf-8",  # noqa: E731
                                           errors="replace", env=env)  # noqa: E731
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
        with tempfile.TemporaryDirectory() as d, cwd(d):
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


class V03(unittest.TestCase):
    """0.3.0: requests from dev-process-light 0.8 (A1~C3)"""

    def test_version_matches(self):
        v = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
        self.assertEqual(dl.__version__, v)
        self.assertIn(v, run("--version").stdout)
        for f in (".claude-plugin/plugin.json", ".claude-plugin/marketplace.json"):
            self.assertIn(f'"{v}"', (ROOT / f).read_text(encoding="utf-8"))

    def test_a1_plan_outside_project_keeps_only_name(self):
        with tempfile.TemporaryDirectory() as src, tempfile.TemporaryDirectory() as proj, cwd(proj):
            p = Path(src) / "secret-folder-name" / "m.csv"
            p.parent.mkdir()
            p.write_text("이름,메모\n김하나,안녕\n", encoding="utf-8")
            plan = dl.import_plan(str(p), "member")
            self.assertEqual(plan["file"], "m.csv")
            self.assertNotIn("secret-folder-name", json.dumps(plan, ensure_ascii=False))
            plan["columns"][0]["name"], plan["columns"][1]["name"] = "member_name", "memo"
            plan["approved"] = True
            Path("data").mkdir()
            with self.assertRaises(SystemExit):           # not in the project -> must be told where
                dl.import_apply(plan, "data/model.light.json", "data/app.db", "네")
            log = dl.import_apply(plan, "data/model.light.json", "data/app.db", "네", file=str(p))
            self.assertEqual(log["file"], "m.csv")
            self.assertNotIn("secret-folder-name", Path("data/import_log.jsonl").read_text(encoding="utf-8"))

    def test_a1_cli_default_out_in_data(self):
        with tempfile.TemporaryDirectory() as d:
            Path(d, "x.csv").write_text("제목\n휴무\n", encoding="utf-8")
            r = run("import", "plan", "x.csv", "--table", "notice", cwd=d)
            self.assertEqual(r.returncode, 0, r.stderr)
            self.assertTrue(Path(d, "data", "import_plan.json").exists())
            self.assertFalse(Path(d, "import_plan.json").exists())
            self.assertIn("저장소에 올리지", r.stdout)

    def test_a3_rls_on_every_table(self):
        m = shop()
        sql = dl.ddl(m, "postgresql")
        for t in m["tables"]:
            self.assertIn(f"ALTER TABLE {t['name']} ENABLE ROW LEVEL SECURITY;", sql)
        self.assertIn("service_role", sql)
        self.assertNotIn("_read ON pi_customer", sql)            # no read-all template for personal data
        self.assertNotIn("ROW LEVEL", dl.ddl(m, "sqlite"))

    def test_a4_hook_never_suggests_skipping(self):
        self.assertNotIn("--no-verify", dl.HOOK)
        self.assertIn(dl.__version__, dl.HOOK)

    def test_b2_unique_combo(self):
        m = shop()
        self.assertIn("UNIQUE (orders_id, dish_id)", dl.ddl(m, "sqlite"))
        ok, lines = dl.try_sqlite(m)
        self.assertTrue(ok, lines)
        self.assertTrue(any("함께 중복" in l and l.startswith("OK") for l in lines))
        self.assertEqual(dl.tables(dl.upgrade(m) and m)["order_item"]["unique"], [["orders_id", "dish_id"]])
        full = {t["name"]: t for t in dl.upgrade(m)["tables"]}
        self.assertEqual(full["order_item"]["uniques"], [["orders_id", "dish_id"]])
        bad = shop()
        dl.tables(bad)["order_item"]["unique"] = [["orders_id"], ["nope", "dish_id"], "x"]
        errs = dl.check(bad)[0]
        self.assertTrue(any("표의 unique" in e for e in errs))
        bad = shop()
        dl.tables(bad)["order_item"]["unique"] = [["orders_id"], ["nope", "dish_id"]]
        errs = dl.check(bad)[0]
        self.assertTrue(any("칸 하나면" in e for e in errs))
        self.assertTrue(any("nope" in e for e in errs))

    def test_b3_schema_roundtrip(self):
        """model -> SQLite -> import schema -> same structure, and verify sees no data-losing drift"""
        with tempfile.TemporaryDirectory() as d:
            m = shop()
            db = Path(d) / "app.db"
            db_script(db, dl.ddl(m, "sqlite"))
            draft, issues = dl.schema_to_model(db)
            self.assertEqual(issues, [])
            self.assertEqual(dl.check(draft)[0], [])
            got = {t["name"]: {c["name"]: c["type"] for c in t["columns"]} for t in draft["tables"]}
            lossy = {"long_text": "text"}                    # SQLite cannot tell long text from short text
            want = {t["name"]: {c["name"]: lossy.get(c["type"], c["type"]) for c in t["columns"]} for t in m["tables"]}
            self.assertEqual(got, want)
            dt_ = dl.tables(draft)
            self.assertEqual(dt_["order_item"]["unique"], [["orders_id", "dish_id"]])
            self.assertTrue(next(c for c in dt_["customer"]["columns"] if c["name"] == "nickname")["unique"])
            self.assertEqual(next(c for c in dt_["order_item"]["columns"] if c["name"] == "orders_id")["on_delete"], "delete")
            self.assertTrue(next(c for c in dt_["pi_customer"]["columns"] if c["name"] == "customer_id")["key"])
            grade = next(c for c in dt_["customer"]["columns"] if c["name"] == "grade")
            self.assertEqual((grade["choices"], grade["default"]), (["일반", "단골"], "일반"))
            self.assertIs(next(c for c in dt_["dish"]["columns"] if c["name"] == "on_sale")["default"], True)
            mp = Path(d) / "model.light.json"
            dl.save(draft, mp)
            self.assertEqual(dl.db_drift(draft, db)[0], [])

    def test_b3_schema_flags_bad_names(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "app.db"
            db_script(db, 'CREATE TABLE "order"(id INTEGER PRIMARY KEY, Memo TEXT); CREATE TABLE logs(msg TEXT);')
            draft, issues = dl.schema_to_model(db)
            text = "\n".join(issues)
            self.assertIn("order:", text)
            self.assertIn("order.Memo", text)
            self.assertIn("logs: 행을 구별할 키", text)
            r = run("import", "schema", db, "--out", Path(d) / "m.json")
            self.assertEqual(r.returncode, 0)
            self.assertEqual(run("import", "schema", db, "--out", Path(d) / "m.json").returncode, 1)   # no overwrite

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_b4_b5_hook_options(self):
        with tempfile.TemporaryDirectory() as d:
            g = lambda *a: subprocess.run(["git", *a], cwd=d, capture_output=True, text=True,  # noqa: E731
                                          encoding="utf-8", errors="replace")
            g("init", "-q")
            self.assertFalse(dl.hook_status(d)[0])
            dl.hook_install(d, ci=False)
            self.assertFalse(Path(d, ".github").exists())
            dl.hook_install(d)                                   # remembers --no-ci
            self.assertFalse(Path(d, ".github").exists())
            self.assertTrue(dl.hook_status(d)[0])
            gi = Path(d, ".gitignore").read_text(encoding="utf-8")
            for line in dl.GITIGNORE_LINES:                      # A2
                self.assertIn(line, gi.splitlines())
            hook = Path(d, ".git", "hooks", "pre-commit")
            hook.write_text(hook.read_text(encoding="utf-8").replace(dl.__version__, "0.0.1"), encoding="utf-8")
            same, lines = dl.hook_status(d)
            self.assertFalse(same)
            self.assertTrue(any("0.0.1" in l for l in lines))
            # someone else's hook in core.hooksPath
            g("config", "core.hooksPath", ".githooks")
            Path(d, ".githooks").mkdir()
            Path(d, ".githooks", "pre-commit").write_text("#!/bin/sh\necho lint\n", encoding="utf-8")
            done = dl.hook_install(d)
            self.assertTrue(any("건드리지 않았습니다" in x for x in done))
            dl.hook_install(d, append=True)
            dl.hook_install(d, append=True)                      # again: replaces our block, no duplicate
            text = Path(d, ".githooks", "pre-commit").read_text(encoding="utf-8")
            self.assertTrue(text.startswith("#!/bin/sh\necho lint"))
            self.assertEqual(text.count(dl.HOOK_MARK), 1)
            self.assertTrue(dl.hook_status(d)[0])

    def test_c1_split_wording(self):
        m = shop()
        dl.tables(m)["dish"]["columns"].append({"name": "chef_name", "label": "x", "type": "text", "personal": "name"})
        dl.split(m)
        self.assertTrue(dl.tables(m)["pi_dish"]["about"].startswith("반찬의 개인정보"))


def git_env():
    return {**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t",
            "GIT_COMMITTER_EMAIL": "t@t"}


def gitrun(d, *a):
    return subprocess.run(["git", *a], cwd=d, capture_output=True, text=True, encoding="utf-8", errors="replace",
                          env=git_env())


def supa(m):
    """shop model made into a Supabase sign-up site: owner on customer, own access, read-only menu"""
    m["db"] = "postgresql"
    m["signup"] = "open"
    c = dl.tables(m)["customer"]
    c["columns"].insert(1, {"name": "owner_id", "label": "만든 사람", "type": "owner"})
    c["access"] = "own"
    dl.tables(m)["pi_customer"]["access"] = "own"
    dl.tables(m)["dish"]["access"] = "read"
    return m


class V04(unittest.TestCase):
    """0.4.0: second round of requests from dev-process-light 0.9 (U1~U8)"""

    def test_u1_members_needs_closed_signup(self):
        m = supa(shop())
        dl.tables(m)["orders"]["access"] = "members"
        errs = dl.check(m)[0]
        self.assertTrue(any("새 가입을 끈" in e for e in errs))
        m["signup"] = "closed"
        self.assertEqual(dl.check(m)[0], [])
        sql = dl.ddl(m, "postgresql")
        self.assertIn("CREATE POLICY orders_members ON orders FOR ALL TO authenticated", sql)
        self.assertIn("signup: closed", sql)
        tmpl = dl.ddl(shop(), "postgresql")                   # templates only: the warning travels with the template
        self.assertIn("[정해진 사람끼리 · 새 가입을 끈 경우에만]", tmpl)
        self.assertIn("pi_customer_members", tmpl)            # pi_ also gets the members template (with the condition)

    def test_u1_read_never_on_personal(self):
        m = supa(shop())
        dl.tables(m)["pi_customer"]["access"] = "read"
        self.assertTrue(any("개인정보 표는 누구나 읽기" in e for e in dl.check(m)[0]))

    def test_u2_owner_and_real_policies(self):
        m = supa(shop())
        self.assertEqual(dl.check(m)[0], [])
        sql = dl.ddl(m, "postgresql")
        self.assertIn("owner_id uuid NOT NULL DEFAULT auth.uid()", sql)
        self.assertIn("CREATE POLICY customer_own ON customer FOR ALL TO authenticated USING (owner_id = auth.uid())", sql)
        self.assertIn("EXISTS (SELECT 1 FROM customer b WHERE b.customer_id = pi_customer.customer_id AND b.owner_id = auth.uid())", sql)
        self.assertIn("CREATE POLICY dish_read ON dish FOR SELECT TO anon, authenticated USING (true);", sql)
        self.assertIn("owner_id TEXT", dl.ddl(m, "sqlite"))
        self.assertTrue(dl.try_sqlite(m)[0])                  # SQLite has no sign-in: owner is optional text there
        dl.tables(m)["orders"]["access"] = "own"              # orders has no owner column
        self.assertTrue(any("owner 칸이 있어야" in e for e in dl.check(m)[0]))
        full = dl.upgrade(supa(shop()))
        own = next(c for c in full["tables"][0]["columns"] if c["name"] == "owner_id")
        self.assertFalse(own["nullable"])
        self.assertTrue(any("access" in a for a in full["assumptions"]))

    @unittest.skipUnless(os.environ.get("PG_DSN_HOST"), "PG_DSN_HOST (psql -h 대상) 미설정")
    def test_u2_policies_run_on_postgres(self):
        """auth.uid() / anon / authenticated imitated; the generated SQL must run as is"""
        host, port = os.environ["PG_DSN_HOST"], os.environ.get("PG_DSN_PORT", "5432")
        q = lambda sql: subprocess.run(["psql", "-h", host, "-p", port, "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-q"],  # noqa: E731
                                       input=sql, capture_output=True, text=True)
        prep = ("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth;"
                "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql AS 'select null::uuid';"
                "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;"
                "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF; END $$;")
        self.assertEqual(q(prep).returncode, 0)
        m = supa(shop())
        dl.tables(m)["orders"]["access"] = "members"
        m["signup"] = "closed"
        r = q(dl.ddl(m, "postgresql"))
        self.assertEqual(r.returncode, 0, r.stderr)
        r = q("SELECT count(*) FROM pg_policies;")
        self.assertEqual(r.returncode, 0)

    def test_u3_outside_tables(self):
        with tempfile.TemporaryDirectory() as d:
            m = shop()
            db = Path(d) / "app.db"
            db_script(db, dl.ddl(m, "sqlite") + "CREATE TABLE log (msg TEXT); INSERT INTO log VALUES ('x');")
            self.assertTrue(any("log" in b for b in dl.db_drift(m, db)[0]))
            m["outside"] = ["log"]
            bad, notes = dl.db_drift(m, db)
            self.assertEqual(bad, [])
            self.assertTrue(any("정본 밖" in n for n in notes))
            m["outside"] = ["dish"]
            self.assertTrue(any("outside" in e for e in dl.check(m)[0]))

    def test_u4_rls_comment_says_paste_not_edit(self):
        sql = dl.ddl(shop(), "postgresql")
        self.assertNotIn("앞의 '-- ' 를 지우고", sql)
        self.assertIn("data/supabase-policies.sql", sql)

    def test_u5_doc(self):
        doc = (SKILL / "references" / "with-dev-process-light.md").read_text(encoding="utf-8")
        self.assertIn(".data-light/", doc)
        self.assertIn("data-light.yml", doc)
        self.assertNotIn("다를 때만 `hook install` → `build`", doc)

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_u6_hook_paths(self):
        with tempfile.TemporaryDirectory() as d:
            gitrun(d, "init", "-q")
            for sub in ("동아리/data", "data", ".claude/skills/data-light/examples/shop/data"):
                Path(d, sub).mkdir(parents=True)
            good = shop()
            dl.save(good, Path(d, "동아리/data/model.light.json"))
            dl.build(good, Path(d, "동아리/data/out"))
            bad = shop()
            bad["tables"][0]["name"] = "user"
            dl.save(bad, Path(d, ".claude/skills/data-light/examples/shop/data/model.light.json"))  # installed example: ignored
            dl.hook_install(d, ci=False)
            gitrun(d, "add", "-A")
            r = gitrun(d, "commit", "-qm", "ok")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            # Korean path: broken model must be caught (core.quotepath used to hide it)
            dl.save(bad, Path(d, "동아리/data/model.light.json"))
            gitrun(d, "add", "-A")
            self.assertNotEqual(gitrun(d, "commit", "-qm", "bad").returncode, 0)
            gitrun(d, "reset", "-q", "--hard")
            # only out/ edited by hand -> checked too
            p = Path(d, "동아리/data/out/schema.sql")
            p.write_text(p.read_text(encoding="utf-8") + "-- 손으로 고침\n", encoding="utf-8")
            gitrun(d, "add", "-A")
            r = gitrun(d, "commit", "-qm", "out only")
            self.assertNotEqual(r.returncode, 0, r.stdout)
            self.assertIn("정본과 다릅니다", r.stdout + r.stderr)

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_u8_shared_hook_keeps_tail_and_runs_it(self):
        with tempfile.TemporaryDirectory() as d:
            gitrun(d, "init", "-q")
            hook = Path(d, ".git/hooks/pre-commit")
            hook.parent.mkdir(parents=True, exist_ok=True)
            hook.write_text("#!/bin/sh\necho before > before.txt\n", encoding="utf-8")
            dl.hook_install(d, ci=False, append=True)
            with open(hook, "a", encoding="utf-8") as f:
                f.write("echo after > after.txt\n")
            dl.hook_install(d, ci=False)                       # reinstall: keeps both sides, one block
            text = hook.read_text(encoding="utf-8")
            self.assertEqual(text.count(dl.HOOK_MARK), 1)
            self.assertIn("echo after", text)
            self.assertIn("echo before", text)
            hook.chmod(0o755)
            Path(d, "a.txt").write_text("x", encoding="utf-8")
            gitrun(d, "add", "a.txt")
            r = gitrun(d, "commit", "-qm", "no model change")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertTrue(Path(d, "after.txt").exists())      # our block no longer ends the whole hook
            label = dl._hook_label(Path(d), dl._hooks_dir(Path(d))[1])
            self.assertEqual(label, ".git/hooks/pre-commit")

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_u8_worktree_and_hookspath_label(self):
        with tempfile.TemporaryDirectory() as d:
            main, wt = Path(d, "main"), Path(d, "wt")
            main.mkdir()
            gitrun(main, "init", "-q")
            Path(main, "a.txt").write_text("x", encoding="utf-8")
            gitrun(main, "add", "a.txt")
            gitrun(main, "commit", "-qm", "init")
            gitrun(main, "worktree", "add", "-q", str(wt))
            done = dl.hook_install(wt, ci=False)
            self.assertTrue(any("pre-commit" in x for x in done))
            self.assertTrue(dl.hook_status(wt)[0])
            gitrun(main, "config", "core.hooksPath", ".githooks")
            self.assertEqual(dl._hook_label(main, dl._hooks_dir(main)[1]), ".githooks/pre-commit (git 설정 core.hooksPath)")

    def test_u7_import_guards(self):
        with tempfile.TemporaryDirectory() as d, cwd(d):
            Path("data").mkdir()
            m = shop()
            m["db"] = "postgresql"
            dl.save(m, "data/model.light.json")
            Path("n.csv").write_text("제목\n휴무\n", encoding="utf-8")
            plan = dl.import_plan("n.csv", "notice")
            plan["columns"][0]["name"] = "title"
            plan["approved"] = True
            with self.assertRaises(SystemExit) as e:
                dl.import_apply(plan, "data/model.light.json", "data/app.db", "네")
            self.assertIn("PostgreSQL", str(e.exception))
            self.assertFalse(Path("data/app.db").exists())
            log = dl.import_apply(plan, "data/model.light.json", "data/app.db", "네", force_sqlite=True)
            self.assertEqual(log["rows"], 1)
            # second time: stops before making a backup; backup path in the log is project-relative
            with self.assertRaises(SystemExit):
                dl.import_apply(plan, "data/model.light.json", "data/app.db", "네", force_sqlite=True)
            self.assertFalse(Path("data/backup").exists())
            log = dl.import_apply(plan, "data/model.light.json", str(Path("data/app.db").resolve()), "네",
                                  append=True, force_sqlite=True)
            self.assertTrue(log["backup"].startswith("data/backup/"), log["backup"])

    def test_u7_schema_flags_personal(self):
        with tempfile.TemporaryDirectory() as d:
            db = Path(d) / "app.db"
            db_script(db, "CREATE TABLE member (member_id INTEGER PRIMARY KEY, CustomerName TEXT, phone TEXT,"
                          " dish_name TEXT, hotel TEXT);")
            issues = "\n".join(dl.schema_to_model(db)[1])
            self.assertIn("member.CustomerName: 개인정보(name)", issues)
            self.assertIn("member.phone: 개인정보(phone)", issues)
            self.assertNotIn("dish_name: 개인정보", issues)
            self.assertNotIn("hotel: 개인정보", issues)


class V041(unittest.TestCase):
    """0.4.1: third round (V1~V6)"""

    def test_v1_case_patterns_have_open_paren(self):
        """bash 3.2 (macOS /bin/sh) reads a bare 'pattern)' inside $( ) as the end of the substitution"""
        lines = [l.strip() for l in dl.HOOK.splitlines()]
        pats = [l for l in lines if re.match(r"^\(?[^\s()]*[*/][^\s]*\)", l) or l.startswith("case ")]
        self.assertTrue(pats)
        for l in lines:
            if l.startswith("case ") and " in " in l and l.rstrip().endswith("esac"):
                self.assertIn(" in (", l, l)
            elif re.match(r"^[^#(\s][^\s]*\) ", l):
                self.fail("case 패턴에 '(' 가 없습니다: " + l)

    def test_v1_hook_parses_with_every_sh(self):
        with tempfile.TemporaryDirectory() as d:
            f = Path(d) / "pre-commit"
            dl._write(f, "#!/bin/sh\n" + dl.HOOK)
            for sh in ("sh", "dash", "bash", "busybox"):
                exe = shutil.which(sh)
                if not exe:
                    continue
                # file name + cwd: on Windows "bash" may be WSL, which cannot read C:\\... paths
                args = [exe, "sh", "-n", f.name] if sh == "busybox" else [exe, "-n", f.name]
                if sh == "bash":
                    args = [exe, "--posix", "-n", f.name]
                r = subprocess.run(args, capture_output=True, text=True, cwd=d)
                if r.returncode == 127 or "No such file" in r.stderr:      # a shell that cannot see this folder
                    continue
                self.assertEqual(r.returncode, 0, f"{sh}: {r.stderr}")
            self.assertEqual(dl._hook_syntax_error(f), "")

    @unittest.skipUnless(shutil.which("git") and shutil.which("sh"), "git/sh 없음")
    def test_v1_unparsable_hook_is_not_left_behind(self):
        """if this computer's sh cannot read our block, install must not leave a hook that stops every commit"""
        with tempfile.TemporaryDirectory() as d:
            gitrun(d, "init", "-q")
            old = dl.HOOK
            try:
                dl.HOOK = dl.HOOK.replace("(\n  models=", "(\n  case x in x) ;; esac )\n  models=", 1)  # broken on purpose
                done = dl.hook_install(d, ci=False)
            finally:
                dl.HOOK = old
            self.assertTrue(any("설치하지 않았습니다" in x for x in done), done)
            self.assertFalse(Path(d, ".git/hooks/pre-commit").exists())

    def test_v2_split_carries_access(self):
        m = supa(shop())
        del dl.tables(m)["pi_customer"]["access"]
        dl.tables(m)["dish"]["columns"].append({"name": "chef_name", "label": "요리사", "type": "text", "personal": "name"})
        dl.tables(m)["orders"]["access"] = "own"
        dl.tables(m)["orders"]["columns"].insert(1, {"name": "owner_id", "label": "주문한 계정", "type": "owner"})
        dl.tables(m)["orders"]["columns"].append({"name": "receiver", "label": "받는 사람", "type": "text", "personal": "name"})
        dl.split(m)
        self.assertNotIn("access", dl.tables(m)["pi_dish"])           # read is never copied to personal data
        self.assertEqual(dl.tables(m)["pi_orders"]["access"], "own")
        m2 = supa(shop())
        del dl.tables(m2)["pi_customer"]["access"]
        dl.tables(m2)["customer"]["columns"].append({"name": "email", "label": "메일", "type": "text", "personal": "email"})
        dl.split(m2)                                                  # pi_ already existed without access
        self.assertEqual(dl.tables(m2)["pi_customer"]["access"], "own")
        dl.tables(m2)["dish"]["access"] = ["read", "own"]
        dl.tables(m2)["dish"]["columns"].insert(1, {"name": "owner_id", "label": "올린 사람", "type": "owner"})
        dl.tables(m2)["dish"]["columns"].append({"name": "cook", "label": "요리사", "type": "text", "personal": "name"})
        dl.split(m2)
        self.assertEqual(dl.tables(m2)["pi_dish"]["access"], "own")

    def test_v3_read_and_write_lists(self):
        m = supa(shop())
        d = dl.tables(m)["dish"]
        d["columns"].insert(1, {"name": "owner_id", "label": "올린 사람", "type": "owner"})
        d["access"] = ["read", "own"]                                 # a board: everyone reads, only the writer edits
        self.assertEqual(dl.check(m)[0], [])
        sql = dl.ddl(m, "postgresql")
        self.assertIn("CREATE POLICY dish_read_read ON dish FOR SELECT TO anon, authenticated USING (true);", sql)
        self.assertIn("CREATE POLICY dish_add_own ON dish FOR INSERT TO authenticated WITH CHECK (owner_id = auth.uid());", sql)
        self.assertIn("CREATE POLICY dish_delete_own ON dish FOR DELETE TO authenticated USING (owner_id = auth.uid());", sql)
        self.assertNotIn("dish_read ON dish FOR SELECT", sql.replace("dish_read_read", ""))
        for bad in (["read", "read"], ["read", "own", "members"], ["read", "admin"], []):
            d["access"] = bad
            self.assertTrue(any("access" in e for e in dl.check(m)[0]), bad)
        d["access"] = ["read", "members"]                             # members still needs closed sign-up
        self.assertTrue(any("새 가입을 끈" in e for e in dl.check(m)[0]))
        m["signup"] = "closed"
        self.assertEqual(dl.check(m)[0], [])
        dl.tables(m)["pi_customer"]["access"] = ["read", "own"]
        self.assertTrue(any("개인정보 표는 누구나 읽기" in e for e in dl.check(m)[0]))

    @unittest.skipUnless(os.environ.get("PG_DSN_HOST"), "PG_DSN_HOST 미설정")
    def test_v3_policies_behave_on_postgres(self):
        """anon reads the board, a signed-in user edits only own rows"""
        host, port = os.environ["PG_DSN_HOST"], os.environ.get("PG_DSN_PORT", "5432")
        q = lambda sql: subprocess.run(["psql", "-h", host, "-p", port, "-U", "postgres", "-v", "ON_ERROR_STOP=1", "-qtA"],  # noqa: E731
                                       input=sql, capture_output=True, text=True)
        prep = ("DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public; DROP SCHEMA IF EXISTS auth CASCADE; CREATE SCHEMA auth;"
                "CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS "
                "$$ select nullif(current_setting('request.uid', true), '')::uuid $$;"
                "DO $$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='anon') THEN CREATE ROLE anon; END IF;"
                "IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='authenticated') THEN CREATE ROLE authenticated; END IF; END $$;"
                "GRANT USAGE ON SCHEMA public, auth TO anon, authenticated; GRANT EXECUTE ON FUNCTION auth.uid() TO anon, authenticated;")
        self.assertEqual(q(prep).returncode, 0)
        board = {"format": "data-light/1", "project": "게시판", "db": "postgresql", "signup": "open", "tables": [
            {"name": "post", "label": "글", "access": ["read", "own"], "columns": [
                {"name": "post_id", "type": "id"}, {"name": "owner_id", "label": "쓴 사람", "type": "owner"},
                {"name": "title", "label": "제목", "type": "text", "required": True}]}]}
        self.assertEqual(dl.check(board)[0], [])
        r = q(dl.ddl(board, "postgresql") + "GRANT SELECT, INSERT, UPDATE, DELETE ON post TO anon, authenticated;")
        self.assertEqual(r.returncode, 0, r.stderr)
        a, b = "00000000-0000-0000-0000-00000000000a", "00000000-0000-0000-0000-00000000000b"
        script = (f"SET request.uid = '{a}'; SET ROLE authenticated; INSERT INTO post(title) VALUES ('a의 글'); RESET ROLE;"
                  f"SET request.uid = '{b}'; SET ROLE authenticated; UPDATE post SET title = 'b가 고침'; RESET ROLE;"
                  "SET request.uid = ''; SET ROLE anon; SELECT title FROM post; RESET ROLE;")
        r = q(script)
        self.assertEqual(r.returncode, 0, r.stderr)
        self.assertEqual(r.stdout.strip().splitlines()[-1], "a의 글")      # anon can read; b could not edit a's row
        r = q("SET ROLE anon; INSERT INTO post(owner_id, title) VALUES (gen_random_uuid(), 'x');")
        self.assertNotEqual(r.returncode, 0)                           # anon cannot write

    def test_v4_table_without_samples_or_required(self):
        m = shop()
        m["tables"].append({"name": "notice", "label": "공지", "columns": [
            {"name": "notice_id", "type": "id"}, {"name": "memo", "label": "메모", "type": "text"}]})
        ok, lines = dl.try_sqlite(m)
        self.assertTrue(ok, "\n".join(l for l in lines if l.startswith("FAIL")))

    def test_v5_pi_without_access_is_noted(self):
        m = supa(shop())
        del dl.tables(m)["pi_customer"]["access"]
        self.assertTrue(any("이 개인정보 표에는 없습니다" in w for w in dl.check(m)[1]))

    def test_v6_closed_signup_comment(self):
        m = shop()
        m["db"], m["signup"] = "postgresql", "closed"
        sql = dl.ddl(m, "postgresql")
        self.assertIn("Allow anonymous sign-ins", sql)
        self.assertIn("Authentication → Users → Add user", sql)


class V05(unittest.TestCase):
    """0.5.0 -- 만드는 것(product): 전문판 data.product_type 의 부분집합 (설계·적재·관리·분석), 묻고 짐작하지 않는다"""

    def _verify(self, m):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "model.light.json"
            dl.save(m, p)
            dl.build(m, Path(d) / "out")
            return dl.verify(p, use_db=False)

    def test_missing_product_is_undetermined_and_blocks_verify(self):
        m = shop()
        del m["product"]
        errs, warns = dl.check(m)
        self.assertEqual(errs, [])
        self.assertTrue(any("유형 미정" in w for w in warns))
        ok, lines = self._verify(m)
        self.assertFalse(ok)
        self.assertTrue(any(l.startswith("FAIL: 만드는 것(product)이 유형 미정") for l in lines))

    def test_product_shape_rules(self):
        for bad, msg in ((["manage"], "모양"), ({"kinds": ["crud"], "said": "x"}, "product.kinds"),
                         ({"kinds": ["manage", "analyze"], "said": "x"}, "product.main"),
                         ({"kinds": ["manage"], "main": "analyze", "said": "x"}, "kinds 중 하나"),
                         ({"kinds": ["manage"], "said": " "}, "product.said"), ({"kinds": [["design"]], "said": "x"}, "product.kinds"),
                         ({"kinds": ["manage"], "said": 123}, "product.said"), ({"kinds": ["manage"], "said": "x", "main_said": [" "]}, "product.main_said"),
                         ({"kinds": ["manage", "analyze"], "main": {"x": 1}, "said": "x"}, "product.main")):
            m = shop()
            m["product"] = bad
            errs, _ = dl.check(m)
            self.assertTrue(any(msg in e for e in errs), (bad, errs))
        m = shop()
        m["product"] = {"kinds": ["design"], "said": "설계 파일만 주세요"}
        self.assertEqual(dl.check(m)[0], [])
        self.assertEqual(dl.product_main(m), "design")

    def test_analyze_needs_goals(self):
        m = shop()
        m["product"] = {"kinds": ["analyze"], "said": "매출을 보고 싶어요"}
        m["goals"] = []
        ok, lines = self._verify(m)
        self.assertFalse(ok)
        self.assertTrue(any("분석이 목적인데 성공 기준" in l for l in lines))

    def test_spec_and_upgrade_carry_product_to_full_ledger(self):
        m = shop()
        self.assertIn("만드는 것: **데이터 관리", dl.spec_md(m))
        fx = dl.upgrade_facts(m)
        pt, pp = fx["facts"]["data.product_type"], fx["facts"]["data.product_primary"]
        self.assertEqual(pt["value"], ["data_management", "analytics_bi"])
        self.assertEqual((pt["source"], pt["quote"]), ("user", m["product"]["said"]))
        self.assertEqual((pp["value"], pp["derived_from"], pp["quote"]), ("data_management", ["data.product_type@1"], m["product"]["main_said"]))
        m2 = shop()
        del m2["product"]["main_said"]
        self.assertNotIn("data.product_primary", dl.upgrade_facts(m2)["facts"])   # 주 목적을 사용자가 말하지 않았으면 옮기지 않는다
        del m["product"]
        self.assertIsNone(dl.upgrade_facts(m))
        with tempfile.TemporaryDirectory() as d:
            r = run("upgrade", SHOP, "--out", Path(d) / "model.json", "--facts", Path(d) / "facts.json")
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("data.product_type@1", r.stdout)
            (Path(d) / "model.json").unlink()
            self.assertEqual(run("upgrade", SHOP, "--out", Path(d) / "model.json", "--facts", Path(d) / "facts.json").returncode, 1)
            self.assertFalse((Path(d) / "model.json").exists())                   # 대장이 있으면 아무것도 만들지 않는다
            scripts = os.environ.get("DEF_SCRIPTS")
            if scripts:                                                            # 전문판 facts.py 가 같은 판정을 내는지
                r = subprocess.run([sys.executable, str(Path(scripts) / "facts.py"), "product", "--facts", str(Path(d) / "facts.json"),
                                    "--json"], capture_output=True, text=True, encoding="utf-8")
                self.assertEqual(r.returncode, 0, r.stdout)
                self.assertEqual(json.loads(r.stdout)["primary"], "data_management")


class PathFix(unittest.TestCase):
    @unittest.skipUnless(hasattr(os, "symlink") and os.name == "posix", "symlink 시험은 posix 에서")
    def test_project_path_through_symlinked_folder(self):
        """macOS 의 /var -> /private/var 처럼 한쪽만 실제 경로여도 프로젝트 안 경로로 본다 (0.4.0~0.4.1 CI 실패 원인)"""
        with tempfile.TemporaryDirectory() as d:
            real = Path(d) / "real"
            (real / "data" / "backup").mkdir(parents=True)
            link = Path(d) / "link"
            os.symlink(real, link)
            with cwd(real):
                self.assertEqual(dl._project_path(str(link / "data" / "backup" / "x.db")), ("data/backup/x.db", True))
            with cwd(link):
                self.assertEqual(dl._project_path(str(real / "data" / "x.csv")), ("data/x.csv", True))
            shared = Path(d) / "shared"
            shared.mkdir()
            os.symlink(shared, real / "inbox")                                     # 프로젝트 안의 링크 폴더는 이름 그대로
            with cwd(real):
                self.assertEqual(dl._project_path(str(real / "inbox" / "a.csv")), ("inbox/a.csv", True))
            priv = Path(d) / "private"                                            # macOS: 임시 폴더 자체가 /var -> /private/var 링크 아래
            (priv / "proj").mkdir(parents=True)
            os.symlink(priv, Path(d) / "var")
            os.symlink(shared, priv / "proj" / "inbox")
            with cwd(Path(d) / "var" / "proj"):
                self.assertEqual(dl._project_path(str(Path(d) / "var" / "proj" / "inbox" / "a.csv")), ("inbox/a.csv", True))
                self.assertEqual(dl._project_path(str(shared / "b.csv")), ("b.csv", False))


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



class V06(unittest.TestCase):
    """0.6.0 -- 웹 ERD 뷰어 사본 (전문판 dataviewer, MIT) 과 view 명령."""

    def test_viewer_copy_matches_lock(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import update_viewer
        self.assertEqual(update_viewer.check(), [])

    def test_viewer_draws_light_model(self):
        import urllib.request
        sys.path.insert(0, str(dl.VIEWER_DIR))
        from dataviewer.server import Viewer, serve_in_thread
        with tempfile.TemporaryDirectory() as d:
            m = Path(d) / "model.light.json"
            shutil.copy(SHOP, m)
            v = Viewer([m])
            srv, url = serve_in_thread(v)
            try:
                with urllib.request.urlopen(url + "api/model", timeout=5) as r:
                    data = json.loads(r.read().decode("utf-8"))
                with urllib.request.urlopen(url, timeout=5) as r:
                    page = r.read().decode("utf-8")
            finally:
                v.stop(); srv.shutdown(); srv.server_close()
            src = data["sources"][0]
            self.assertEqual(src["kind"], "light")
            self.assertEqual({t["name"] for t in src["tables"]}, {t["name"] for t in shop()["tables"]})
            self.assertTrue(src["relations"])
            self.assertIn("ERD", page)

    def test_view_command_needs_model(self):
        with tempfile.TemporaryDirectory() as d:
            r = run("view", "data/model.light.json", "--no-open", cwd=d)
            self.assertEqual(r.returncode, 1)
            self.assertIn("정본이 없습니다", r.stdout)



class V08(unittest.TestCase):
    """0.8.0 -- 개발 관리 사이트 (가벼운 판 5쪽, 파일 모드, 포트 없음) -- 전문판 화면 틀의 MIT 사본 (site/shell)."""

    def _site(self, d):
        root = Path(d) / "proj"
        (root / "data").mkdir(parents=True)
        shutil.copy(SHOP, root / "data" / "model.light.json")
        return root, root / "data" / "model.light.json"

    def test_shell_copy_matches_lock(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import update_shell
        self.assertEqual(update_shell.check(), [])
        lock = json.loads((SKILL / "site" / "shell.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(lock["version"], (SKILL / "site" / "shell" / "VERSION").read_text(encoding="utf-8").strip())
        self.assertIn("MIT", (SKILL / "site" / "NOTICE.md").read_text(encoding="utf-8"))

    def test_shell_fingerprint_order_is_by_path_text(self):
        sys.path.insert(0, str(ROOT / "tools"))
        import hashlib
        import update_shell
        with tempfile.TemporaryDirectory() as d:
            for rel in ("README.md", "assets/x.js", "VERSION", "page.html"):
                f = Path(d) / rel
                f.parent.mkdir(parents=True, exist_ok=True)
                with open(f, "wb") as fh:
                    fh.write(rel.encode("utf-8") + b"\r\n")
            h = hashlib.sha256()
            for rel in sorted(("README.md", "assets/x.js", "VERSION", "page.html")):           # 글자 순 (Windows 의 대소문자 무시 순서가 아니라)
                h.update(rel.encode("utf-8") + b"\0" + rel.encode("utf-8") + b"\n\0")
            self.assertEqual(update_shell.fingerprint(Path(d)), h.hexdigest()[:16])

    def test_site_has_five_pages_with_spec_headers(self):
        with tempfile.TemporaryDirectory() as d:
            root, m = self._site(d)
            r = run("site", m)
            self.assertEqual(r.returncode, 0, r.stdout + r.stderr)
            self.assertIn("개발 관리 사이트", r.stdout)
            site = root / "data" / "outputs" / "site"
            self.assertEqual((root / "data" / "outputs" / ".gitignore").read_text(encoding="utf-8").strip().splitlines()[-1], "*")
            sj = json.loads((site / "data" / "site.json").read_text(encoding="utf-8"))
            self.assertEqual([x["id"] for x in sj["menu"]], ["overview", "business", "data", "progress", "files"])
            self.assertEqual([x["no"] for x in sj["menu"]], [1, 2, 4, 9, 10])               # 전문판과 같은 번호 · 주소
            self.assertEqual(sj["framework"], "data-light")
            self.assertEqual(sj["level"], "light")
            for pid, path in (("overview", ""), ("business", "business/"), ("data", "data/"), ("progress", "progress/"), ("files", "files/")):
                pg = json.loads((site / "data" / f"{pid}.json").read_text(encoding="utf-8"))
                for k in ("outputs_version", "page", "framework", "framework_version", "level", "generated_at", "source", "confirm", "blanks", "body"):
                    self.assertIn(k, pg)
                self.assertEqual(pg["outputs_version"], 1)
                self.assertTrue(pg["body"]["sections"])
                html_ = (site / path / "index.html").read_text(encoding="utf-8")
                self.assertNotIn("<script>", html_)                                         # 인라인 스크립트 없음 (CSP)
                self.assertIn(f'data/{pid}.js', html_)
            self.assertTrue((site / "assets" / "shell.js").is_file())
            text = "\n".join(f.read_text(encoding="utf-8") for f in site.rglob("*") if f.suffix in (".json", ".js", ".html"))
            self.assertNotRegex(text, r"127\.0\.0\.1:\d|localhost:\d")                      # 포트 없음 (파일 모드)
            data = json.loads((site / "data" / "data.json").read_text(encoding="utf-8"))
            ids = [x.get("id") for x in data["body"]["sections"]]
            self.assertIn("erd", ids)
            self.assertIn("t-customer", ids)
            self.assertIn("s-customer", ids)                                                # 예시 값 (만든 값)
            biz = json.loads((site / "data" / "business.json").read_text(encoding="utf-8"))
            self.assertEqual(biz["body"]["sections"][0]["id"], "works")

    def test_site_shows_blanks_and_check_problems(self):
        with tempfile.TemporaryDirectory() as d:
            root, m = self._site(d)
            model = dl.load(m)
            model.pop("works", None)
            model.pop("goals", None)
            model["tables"][0].pop("sample", None)
            dl.save(model, m)
            r = dl.build_site(m)
            self.assertGreater(r["blanks"], 0)
            site = Path(r["site"])
            ov = json.loads((site / "data" / "overview.json").read_text(encoding="utf-8"))
            self.assertTrue(any("알고 싶은 것" in x["label"] for x in ov["blanks"]["items"]))
            biz = json.loads((site / "data" / "business.json").read_text(encoding="utf-8"))
            self.assertEqual(biz["body"]["sections"][0]["kind"], "empty")                    # 재료가 없어도 쪽은 있고 '만드는 법'

    def test_site_folder_is_its_own(self):
        with tempfile.TemporaryDirectory() as d:
            root, m = self._site(d)
            other = Path(d) / "mine"
            other.mkdir()
            (other / "index.html").write_text("<h1>내 쪽</h1>", encoding="utf-8")
            with self.assertRaises(ValueError):
                dl.build_site(m, other)
            self.assertIn("내 쪽", (other / "index.html").read_text(encoding="utf-8"))
            with self.assertRaises(ValueError):
                dl.build_site(m, root)
            out = Path(d) / "site2"
            dl.build_site(m, out)
            (out / "progress" / "stale.html").write_text("x", encoding="utf-8")               # 이 도구가 쓰지 않은 파일은 지우지 않는다
            dl.build_site(m, out)
            self.assertTrue((out / "progress" / "stale.html").is_file())

    def _pages(self, m, fw="data-light"):
        model = dl.load(m)
        return model, dl.site_pages(model, m, "abc123", "2026-10-20T00:00:00Z", framework=fw, framework_version="9.9.9")

    def test_write_site_takes_subpages_and_menu_lines_for_the_dev_light_portal(self):
        with tempfile.TemporaryDirectory() as d:
            root, m = self._site(d)
            model, pages = self._pages(m, "dev-light")
            self.assertEqual({p["framework"] for p in pages.values()}, {"dev-light"})
            self.assertEqual({p["framework_version"] for p in pages.values()}, {"9.9.9"})
            sub = dl.site_page("progress", [{"kind": "text", "id": "t", "text": "기록"}], framework="dev-light", framework_version="9.9.9",
                               mark="abc123", now="2026-10-20T00:00:00Z", source=[], sub="log/1", title="기록 하나")
            out = root / "dev-notes" / "outputs" / "site"
            r = dl.write_site(out, root, pages, framework="dev-light", framework_version="9.9.9", project="p", mark="abc123", now="2026-10-20T00:00:00Z",
                              subs=[("progress", "log/1", sub), ("progress", "../x", sub), ("overview", "a", sub)],
                              menu_subs={"progress": [{"id": "log", "label": "기능별 기록", "href": "progress/#logs", "n": 1}]},
                              default_site=out)
            self.assertEqual((r["pages"], r["subs"]), (5, 1))
            self.assertEqual(len(r["errors"]), 2)                                           # 위로 가는 이름 · 개요 아래는 쓰지 않는다
            html_ = (out / "progress" / "log" / "1" / "index.html").read_text(encoding="utf-8")
            self.assertIn('data-base="../../../"', html_)
            self.assertIn("data/progress/log/1.js", html_)
            self.assertTrue((root / "dev-notes" / "outputs" / ".gitignore").is_file())     # 정한 자리면 outputs/ 에 .gitignore
            sj = json.loads((out / "data" / "site.json").read_text(encoding="utf-8"))
            self.assertEqual(sj["framework_label"], "dev-process-light")
            self.assertEqual(sj["menu"][3]["subs"][0]["n"], 1)
            with self.assertRaises(ValueError):
                dl.write_site(out, root, {k: v for k, v in pages.items() if k != "files"}, framework="dev-light", framework_version="1",
                              project="p", mark="m", now="n")
            with self.assertRaises(ValueError):
                dl.write_site(root.parent, root, pages, framework="dev-light", framework_version="1", project="p", mark="m", now="n")

    def test_old_files_go_only_when_unchanged(self):
        with tempfile.TemporaryDirectory() as d:
            root, m = self._site(d)
            model, pages = self._pages(m)
            out = Path(d) / "s"
            sub = lambda n: dl.site_page("progress", [], framework="data-light", framework_version="1", mark="m", now="n", source=[], sub=n)  # noqa: E731
            dl.write_site(out, root, pages, framework="data-light", framework_version="1", project="p", mark="m", now="n",
                          subs=[("progress", "a", sub("a")), ("progress", "b", sub("b"))])
            (out / "data" / "progress" / "b.json").write_text("내가 고침", encoding="utf-8")
            dl.write_site(out, root, pages, framework="data-light", framework_version="1", project="p", mark="m", now="n")
            self.assertFalse((out / "progress" / "a" / "index.html").exists())               # 그대로인 지난 파일은 지운다
            self.assertTrue((out / "data" / "progress" / "b.json").is_file())                # 고친 파일은 둔다


class V09(unittest.TestCase):
    """0.9.0 -- 새 판 반영이 원칙, 직접 고친 것은 말없이 정하지 않고 묻는다 (소유자 원칙 2026-10-20): CI 파일 · 지운 .gitignore 줄."""

    def _repo(self, d):
        subprocess.run(["git", "init", "-q"], cwd=d, capture_output=True)
        dl.hook_install(d)
        return Path(d, ".github", "workflows", "data-light.yml"), Path(d, ".gitignore")

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_edited_ci_file_is_asked_then_updated_or_kept(self):
        with tempfile.TemporaryDirectory() as d:
            wf, gi = self._repo(d)
            self.assertEqual(wf.read_text(encoding="utf-8"), dl.CI)
            wf.write_text(dl.CI + "# 우리 팀 단계\n", encoding="utf-8")
            done = dl.hook_install(d)
            self.assertTrue(any(x.startswith(dl.ASK) and "CI 파일" in x for x in done))
            self.assertIn("우리 팀 단계", wf.read_text(encoding="utf-8"))                      # 덮지 않았다
            self.assertFalse(dl.hook_status(d)[0])
            done = dl.hook_install(d, keep=["ci"])
            self.assertFalse(any(x.startswith(dl.ASK) for x in done))
            self.assertTrue(dl.hook_status(d)[0])                                            # 고른 대로 -- 다시 묻지 않는다
            self.assertFalse(any(x.startswith(dl.ASK) for x in dl.hook_install(d)))
            dl.hook_install(d, update=["ci"])
            self.assertEqual(wf.read_text(encoding="utf-8"), dl.CI)
            self.assertTrue(list(Path(d, ".data-light", "backup").rglob("data-light.yml")))
            wf.write_text(dl.CI.replace("verify", "verify ", 1), encoding="utf-8")
            st = json.loads(Path(d, ".data-light", "settings.json").read_text(encoding="utf-8"))
            st["ci_fp"] = dl._fp(wf.read_text(encoding="utf-8"))                             # 지난번에 이 도구가 쓴 그대로 (예전 판)
            Path(d, ".data-light", "settings.json").write_text(json.dumps(st), encoding="utf-8")
            done = dl.hook_install(d)
            self.assertFalse(any(x.startswith(dl.ASK) for x in done))
            self.assertEqual(wf.read_text(encoding="utf-8"), dl.CI)                            # 손대지 않은 예전 판은 묻지 않고 새 판

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_deleted_ci_file_and_ignore_lines_are_not_silently_restored(self):
        with tempfile.TemporaryDirectory() as d:
            wf, gi = self._repo(d)
            wf.unlink()
            gi.write_text(gi.read_text(encoding="utf-8").replace(".env\n", ""), encoding="utf-8")
            done = dl.hook_install(d)
            asks = [x for x in done if x.startswith(dl.ASK)]
            self.assertEqual(len(asks), 2, done)
            self.assertFalse(wf.exists())
            self.assertNotIn(".env", gi.read_text(encoding="utf-8").splitlines())
            self.assertFalse(dl.hook_status(d)[0])
            r = run("hook", "install", "--repo", d)
            self.assertEqual(r.returncode, 3)
            self.assertIn("물어볼 것", r.stdout)
            dl.hook_install(d, ci=True, update=["gitignore"])                                  # 사용자: 둘 다 다시
            self.assertTrue(wf.exists())
            self.assertIn(".env", gi.read_text(encoding="utf-8").splitlines())
            self.assertTrue(dl.hook_status(d)[0])
            gi.write_text(gi.read_text(encoding="utf-8").replace(".env\n", ""), encoding="utf-8")
            dl.hook_install(d, keep=["gitignore"])                                             # 사용자: 지운 채로
            self.assertNotIn(".env", gi.read_text(encoding="utf-8").splitlines())
            self.assertFalse(any(x.startswith(dl.ASK) for x in dl.hook_install(d)))
            self.assertTrue(dl.hook_status(d)[0])
            dl.hook_install(d, ci=False)                                                        # --no-ci 는 그대로 기억
            wf.unlink()
            self.assertFalse(any(x.startswith(dl.ASK) for x in dl.hook_install(d)))


    def _settings(self, d, **change):
        f = Path(d, ".data-light", "settings.json")
        st = json.loads(f.read_text(encoding="utf-8"))
        for k, v in change.items():
            if v is None:
                st.pop(k, None)
            else:
                st[k] = v
        f.write_text(json.dumps(st), encoding="utf-8")

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_upgrade_from_08_still_asks_about_what_was_removed(self):
        with tempfile.TemporaryDirectory() as d:
            wf, gi = self._repo(d)
            self._settings(d, ci_fp=None, gitignore=None)                                       # 0.8 이하는 기록을 남기지 않았다
            wf.unlink()
            gi.write_text(gi.read_text(encoding="utf-8").replace(".env\n", ""), encoding="utf-8")
            done = dl.hook_install(d)
            self.assertEqual(len([x for x in done if x.startswith(dl.ASK)]), 2, done)
            self.assertFalse(wf.exists())
            self.assertNotIn(".env", gi.read_text(encoding="utf-8").splitlines())
            # 예전 사본이 넣지 않던 줄은 새로 더하는 것 -- 묻지 않고 넣는다
            self._settings(d, ci_fp=None, gitignore=None)
            tool = Path(d, ".data-light", "datalight.py")
            tool.write_text(tool.read_text(encoding="utf-8").replace('"import_plan*.json", ".env")', '"import_plan*.json")'), encoding="utf-8")
            done = dl.hook_install(d, ci=True)
            self.assertFalse(any(x.startswith(dl.ASK) for x in done), done)
            self.assertIn(".env", gi.read_text(encoding="utf-8").splitlines())

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_non_utf8_gitignore_is_asked_not_mixed(self):
        with tempfile.TemporaryDirectory() as d:
            wf, gi = self._repo(d)
            raw = "# 우리 것\nnode_modules/\n".encode("cp949")
            gi.write_bytes(raw)
            done = dl.hook_install(d)
            self.assertTrue(any(x.startswith(dl.ASK) and "UTF-8" in x for x in done), done)
            self.assertEqual(gi.read_bytes(), raw)                                               # 섞어 쓰지 않았다
            ok, lines = dl.hook_status(d)                                                        # 읽다가 멈추지 않는다
            self.assertFalse(ok)
            gi.write_bytes(b"\xef\xbb\xbf" + "\n".join(dl.GITIGNORE_LINES).encode("utf-8") + b"\n")   # BOM 이 붙은 UTF-8
            self.assertFalse(any(x.startswith(dl.ASK) for x in dl.hook_install(d)))
            self.assertEqual(gi.read_bytes().count(b"data/app.db"), 1)                           # 첫 줄도 알아본다

    @unittest.skipUnless(shutil.which("git"), "git 없음")
    def test_kept_choices_hold_and_status_separates_asks_from_versions(self):
        with tempfile.TemporaryDirectory() as d:
            wf, gi = self._repo(d)
            gi.write_text(gi.read_text(encoding="utf-8").replace(".env\n", "").replace("data/*.csv\n", ""), encoding="utf-8")
            ok, lines = dl.hook_status(d)
            self.assertFalse(ok)
            self.assertTrue(any(x.startswith("결과: 물어볼 것") for x in lines), lines)           # 버전은 같다 -- 고를 것이 남았다
            dl.hook_install(d, keep=["gitignore"])
            with open(gi, "a", encoding="utf-8") as f:
                f.write(".env\n")                                                              # 한 줄만 다시 넣었다
            self.assertFalse(any(x.startswith(dl.ASK) for x in dl.hook_install(d)))
            self.assertTrue(dl.hook_status(d)[0])
            wf.unlink()
            self.assertTrue(any(x.startswith(dl.ASK) for x in dl.hook_install(d)))
            done = dl.hook_install(d, keep=["ci"])                                               # 사용자: 지운 채로
            self.assertFalse(wf.exists())
            self.assertFalse(any(x.startswith(dl.ASK) for x in done))
            self.assertFalse(any(x.startswith(dl.ASK) for x in dl.hook_install(d)))             # '만들지 않기'로 기억
            self.assertTrue(dl.hook_status(d)[0])
            dl.hook_install(d, ci=True)
            self.assertTrue(wf.exists())


if __name__ == "__main__":
    unittest.main(verbosity=1)
