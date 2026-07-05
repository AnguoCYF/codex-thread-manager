import importlib.util, pathlib, json, sqlite3, shutil, tempfile, os, copy
import tkinter as tk

SCRIPT = pathlib.Path(__file__).resolve().parent.parent / "codex_thread_manager.py"
spec = importlib.util.spec_from_file_location("ctm", SCRIPT)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

PASS = 0; FAIL = 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS: {name}")
    else: FAIL += 1; print(f"  FAIL: {name}")

tmp = pathlib.Path(tempfile.mkdtemp(prefix="e2e_"))
try:
    codex = tmp / ".codex"
    sess = codex / "sessions" / "2026" / "07"
    sess.mkdir(parents=True)
    arch = codex / "archived_sessions"
    arch.mkdir()
    out_dir = tmp / "outputs" / "t1"
    out_dir.mkdir(parents=True)
    (out_dir / "a.txt").write_text("x")

    tid1 = "E2EAAAA-0000-0000-0000-000000000001"
    tid2 = "E2EBBBBB-0000-0000-0000-000000000002"
    rp1 = sess / f"rollout-test-{tid1}.jsonl"
    rp1.write_text('{"role":"user"}')
    rp2 = sess / f"rollout-test-{tid2}.jsonl"
    rp2.write_text('{"role":"user"}')

    db = codex / "state_5.sqlite"
    con = sqlite3.connect(str(db))
    con.execute("CREATE TABLE threads (id TEXT, rollout_path TEXT, created_at INTEGER, updated_at INTEGER, cwd TEXT, title TEXT, archived INTEGER, archived_at INTEGER)")
    con.execute("INSERT INTO threads VALUES (?,?,?,?,?,?,?,?)", (tid1, str(rp1), 1700000000, 1700000100, str(out_dir), "T1", 0, None))
    con.execute("INSERT INTO threads VALUES (?,?,?,?,?,?,?,?)", (tid2, str(rp2), 1700000001, 1700000101, "", "T2", 0, None))
    con.commit(); con.close()

    gs_file = codex / ".codex-global-state.json"
    gs_data = {
        "projectless-thread-ids": [tid1, tid2],
        "thread-workspace-root-hints": {tid1: str(tmp)},
        "thread-projectless-output-directories": {tid1: str(out_dir)},
        "pinned-thread-ids": [tid1],
        "thread-writable-roots": {tid1: [str(tmp)]},
        "keep": "yes",
    }
    gs_file.write_text(json.dumps(gs_data), encoding="utf-8")

    log_db = codex / "logs_2.sqlite"
    con2 = sqlite3.connect(str(log_db))
    con2.execute("CREATE TABLE logs (id INTEGER PRIMARY KEY, thread_id TEXT, body TEXT)")
    con2.execute("INSERT INTO logs (thread_id,body) VALUES (?,?)", (tid1, "l1"))
    con2.execute("INSERT INTO logs (thread_id,body) VALUES (?,?)", (tid2, "l2"))
    con2.commit(); con2.close()

    # monkeypatch module paths
    m.STATE_DB = db
    m.GLOBAL_STATE = gs_file
    m.LOGS_DB = log_db

    root = m.tk.Tk(); root.withdraw()
    app = m.CodexThreadManager(root)
    # point app's globals at mock
    app.global_state = copy.deepcopy(gs_data)

    print("=== E2E Archive mode ===")
    # select tid1
    for k in app.tree.get_children():
        vals = app.tree.item(k, "values")
        if vals[3] == tid1:
            app.tree.set(k, "sel", "Y")
    app._upd_btn()
    check("1 selected", len(app._get_sel()) == 1)
    # run archive
    r = app._exec_delete([tid1], "archive")
    print("  archive result:", r)
    con3 = sqlite3.connect(str(db))
    row = con3.execute("SELECT archived FROM threads WHERE id=?", (tid1,)).fetchone()
    con3.close()
    check("archived=1 in DB", row and row[0] == 1)
    check("rollout still exists (archive keeps file)", rp1.exists())
    check("outputs still exists (archive keeps dir)", out_dir.exists())
    # reset archived for next test
    con4 = sqlite3.connect(str(db))
    con4.execute("UPDATE threads SET archived=0 WHERE id=?", (tid1,))
    con4.commit(); con4.close()
    for k in app.tree.get_children():
        app.tree.set(k, "sel", "")

    print("\n=== E2E Database mode (tid2) ===")
    for k in app.tree.get_children():
        vals = app.tree.item(k, "values")
        if vals[3] == tid2:
            app.tree.set(k, "sel", "Y")
    app._upd_btn()
    r2 = app._exec_delete([tid2], "database")
    print("  database result:", r2)
    con5 = sqlite3.connect(str(db))
    rows = con5.execute("SELECT COUNT(*) FROM threads WHERE id=?", (tid2,)).fetchone()[0]
    con5.close()
    check("tid2 row deleted from DB", rows == 0)
    check("tid2 rollout kept", rp2.exists())
    gs_after = json.loads(gs_file.read_text(encoding="utf-8"))
    check("tid2 removed from projectless", tid2 not in gs_after.get("projectless-thread-ids", []))
    check("keep field preserved", gs_after.get("keep") == "yes")
    for k in app.tree.get_children():
        app.tree.set(k, "sel", "")

    print("\n=== E2E Full mode (tid1) ===")
    for k in app.tree.get_children():
        vals = app.tree.item(k, "values")
        if vals[3] == tid1:
            app.tree.set(k, "sel", "Y")
    app._upd_btn()
    r3 = app._exec_delete([tid1], "full")
    print("  full result:", r3)
    con6 = sqlite3.connect(str(db))
    rows6 = con6.execute("SELECT COUNT(*) FROM threads WHERE id=?", (tid1,)).fetchone()[0]
    con6.close()
    check("tid1 row deleted", rows6 == 0)
    check("tid1 rollout deleted", not rp1.exists())
    check("tid1 outputs dir deleted", not out_dir.exists())
    gs_final = json.loads(gs_file.read_text(encoding="utf-8"))
    check("tid1 not in pinned", tid1 not in gs_final.get("pinned-thread-ids", []))
    check("tid1 not in hints", tid1 not in gs_final.get("thread-workspace-root-hints", {}))
    check("tid1 not in outputs-map", tid1 not in gs_final.get("thread-projectless-output-directories", {}))
    con7 = sqlite3.connect(str(log_db))
    remain = con7.execute("SELECT COUNT(*) FROM logs WHERE thread_id=?", (tid1,)).fetchone()[0]
    con7.close()
    check("tid1 logs cleaned", remain == 0)

    root.destroy()
    print(f"\n{'='*40}")
    print(f"E2E: {PASS} passed, {FAIL} failed")
finally:
    shutil.rmtree(tmp, ignore_errors=True)

import sys
sys.exit(0 if FAIL == 0 else 1)



