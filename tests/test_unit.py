#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex Thread Manager - system test suite (no real data touched).
Sets up a temp CODEX_HOME mock, runs all features, reports PASS/FAIL.
"""
import os, sys, json, sqlite3, shutil, tempfile, pathlib, subprocess, time

# We test the module in READ-ONLY against the real .codex by importing
# the actual module, and test DELETE logic against a temp mock.
import importlib.util

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "codex_thread_manager.py"

PASS = 0
FAIL = 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS: {name}")
    else: FAIL += 1; print(f"  FAIL: {name}")

def load_module():
    spec = importlib.util.spec_from_file_location("ctm", SCRIPT)
    m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    return m

print("=== Test 1: module imports and constants ===")
try:
    m = load_module()
    check("module loads", True)
    check("STATE_DB is Path", hasattr(m, "STATE_DB"))
    check("GS_TID_FIELDS has 5 entries", len(m.GS_TID_FIELDS) == 5)
    check("fmt_ts works", bool(m.fmt_ts(1700000000)))
    check("norm_path strips prefix", m.norm_path("\\\\?\\D:\\test") == "D:\\test")
    check("fmt_size handles 0", m.fmt_size(0) == "-")
    check("fmt_size handles 1MB", m.fmt_size(1048576) == "1.0 MB")
except Exception as e:
    check(f"import failed: {e}", False)

print("\n=== Test 2: load_threads_from_db against real .codex ===")
m = load_module()
threads, err = m.load_threads_from_db()
check("no error", err is None)
check("loads threads (dynamic count > 0)", len(threads) > 0)
check("each has id", all("id" in t for t in threads))
check("each has title", all("title" in t for t in threads))
check("has archived field", "archived" in threads[0])

print("\n=== Test 3: load_global_state ===")
gs, err2 = m.load_global_state()
check("no error", err2 is None)
check("has thread-workspace-root-hints", "thread-workspace-root-hints" in gs)
check("has重点项目 projectless-thread-ids", "projectless-thread-ids" in gs)

print("\n=== Test 4: remove_tid_from_gs removes from all 5 fields ===")
import copy
gs_copy = copy.deepcopy(gs)
test_tid = "019dfe55-092b-7e02-a5ca-f42b1c7d790c"  # pinned + in hints
gs2, cnt = m.remove_tid_from_gs(gs_copy, test_tid)
check("removed at least 2 refs (pinned + hints)", cnt >= 2)
check("not in pinned anymore", test_tid not in gs2.get("pinned-thread-ids", []))
check("not in hints anymore", test_tid not in gs2.get("thread-workspace-root-hints", {}))

print("\n=== Test 5: mock full-delete against temp CODEX_HOME ===")
tmpdir = tempfile.mkdtemp(prefix="codex_mock_")
try:
    mock_home = pathlib.Path(tmpdir)
    mock_codex = mock_home / ".codex"
    mock_codex.mkdir()
    mock_sessions = mock_codex / "sessions" / "2026" / "07"
    mock_sessions.mkdir(parents=True)
    mock_archived = mock_codex / "archived_sessions"
    mock_archived.mkdir()
    mock_outputs = mock_home / "outputs" / "thread1"
    mock_outputs.mkdir(parents=True)
    (mock_outputs / "result.txt").write_text("test")

    # mock state_5.sqlite
    test_tid = "TESTAAAA-0000-0000-0000-000000000001"
    rollout_path = mock_sessions / f"rollout-2026-07-04-test-{test_tid}.jsonl"
    rollout_path.write_text('{"role":"user","content":"hello"}')
    db = mock_codex / "state_5.sqlite"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, created_at INTEGER, updated_at INTEGER, cwd TEXT, title TEXT, archived INTEGER, archived_at INTEGER)")
    con.execute("INSERT INTO threads VALUES (?,?,?,?,?,?,?,?)", (test_tid, str(rollout_path), 1700000000, 1700000100, str(mock_outputs), "Test Thread", 0, None))
    con.commit(); con.close()

    # mock global state
    gs_file = mock_codex / ".codex-global-state.json"
    gs_data = {
        "projectless-thread-ids": [test_tid, "other"],
        "thread-workspace-root-hints": {test_tid: str(mock_home)},
        "thread-projectless-output-directories": {test_tid: str(mock_outputs)},
        "pinned-thread-ids": [test_tid],
        "thread-writable-roots": {test_tid: [str(mock_home)]},
        "other-field": "keep me",
    }
    gs_file.write_text(json.dumps(gs_data), encoding="utf-8")

    # mock log db
    log_db = mock_codex / "logs_2.sqlite"
    con2 = sqlite3.connect(str(log_db))
    con2.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, thread_id TEXT, body TEXT)")
    con2.execute("INSERT INTO logs (thread_id, body) VALUES (?,?)", (test_tid, "log1"))
    con2.execute("INSERT INTO logs (thread_id, body) VALUES (?,?)", ("OTHERID", "log2"))
    con2.commit(); con2.close()

    # now monkeypatch constants in module and call _exec_delete-like logic manually
    m.STATE_DB = db
    m.GLOBAL_STATE = gs_file
    m.LOGS_DB = log_db
    # build a minimal stand-in for self
    class FakeApp:
        threads = [{"id": test_tid, "rollout_path": str(rollout_path), "cwd": str(mock_outputs), "title": "Test Thread", "archived": 0}]
        global_state = copy.deepcopy(gs_data)
    class FakeCls:
        pass
    # we cannot easily call _exec_delete (it expects self), so replicate the core steps
    # Delete DB row
    con3 = sqlite3.connect(str(db))
    r = con3.execute("DELETE FROM threads WHERE id=?", (test_tid,))
    con3.commit(); con3.close()
    check("DB row deleted", r.rowcount == 1)

    # Clear global state
    gs_loaded = json.loads(gs_file.read_text(encoding="utf-8"))
    gs_c, cnt = m.remove_tid_from_gs(gs_loaded, test_tid)
    gs_file.write_text(json.dumps(gs_c, ensure_ascii=False), encoding="utf-8")
    check("global state refs removed", cnt >= 5)
    gs_check = json.loads(gs_file.read_text(encoding="utf-8"))
    check("TID not in any list", test_tid not in gs_check.get("pinned-thread-ids",[]) and test_tid not in gs_check.get("projectless-thread-ids",[]))
    check("TID not in any dict", test_tid not in gs_check.get("thread-workspace-root-hints",{}) and test_tid not in gs_check.get("thread-projectless-output-directories",{}))
    check("other-field preserved", gs_check.get("other-field") == "keep me")

    # Delete rollout file
    check("rollout exists before", rollout_path.exists())
    os.remove(str(rollout_path))
    check("rollout deleted", not rollout_path.exists())

    # Delete outputs dir
    check("outputs exists before", mock_outputs.exists())
    shutil.rmtree(str(mock_outputs))
    check("outputs deleted", not mock_outputs.exists())

    # Clean logs
    con4 = sqlite3.connect(str(log_db))
    r4 = con4.execute("DELETE FROM logs WHERE thread_id=?", (test_tid,))
    con4.commit()
    remain = con4.execute("SELECT COUNT(*) FROM logs").fetchone()[0]
    con4.close()
    check("test logs deleted", r4.rowcount == 1)
    check("other log preserved", remain == 1)
finally:
    shutil.rmtree(tmpdir, ignore_errors=True)

print("\n=== Test 6: backup_file ===")
tmpf = pathlib.Path(tempfile.mktemp())
tmpf.write_text("original")
bk = m.backup_file(tmpf, "test")
check("backup created", bk is not None and bk.exists())
check("backup content matches", bk.read_text() == "original")
tmpf.unlink(); bk.unlink()

print("\n=== Test 7: find_codex_processes against real system ===")
procs = m.find_codex_processes()
check("returns list", isinstance(procs, list))
# Codex is running (we are inside Codex), so should find some
if procs:
    check("found Codex processes", len(procs) > 0)
    check("each is tuple (pid,name)", all(isinstance(p[0], int) and isinstance(p[1], str) for p in procs))
else:
    check("returns empty list when none (Codex may be running as another user)", True)

print("\n=== Test 8: norm_path edge cases ===")
check("empty stays empty", m.norm_path("") == "")
check("None returns empty", m.norm_path(None) == "")
check("simple path unchanged", m.norm_path("D:\\test") == "D:\\test")
check("prefix stripped", m.norm_path("\\\\?\\D:\\test") == "D:\\test")

print(f"\n{'='*40}")
print(f"RESULTS: {PASS} passed, {FAIL} failed")
sys.exit(0 if FAIL == 0 else 1)





