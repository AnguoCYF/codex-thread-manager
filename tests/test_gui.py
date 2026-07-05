import importlib.util, pathlib, json, sqlite3, shutil, tempfile, os, copy
import tkinter as tk

# Load the real module
p = pathlib.Path(__file__).resolve().parent.parent / "codex_thread_manager.py"
spec = importlib.util.spec_from_file_location("ctm", p)
m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)

PASS = 0; FAIL = 0
def check(name, cond):
    global PASS, FAIL
    if cond: PASS += 1; print(f"  PASS: {name}")
    else: FAIL += 1; print(f"  FAIL: {name}")

# Back up real files
real_db = m.STATE_DB
real_gs = m.GLOBAL_STATE
real_logs = m.LOGS_DB
import datetime
ts = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
db_bak = real_db.parent / f"{real_db.name}.gui-test-{ts}"
gs_bak = real_gs.parent / f"{real_gs.name}.gui-test-{ts}"
shutil.copy2(real_db, db_bak)
shutil.copy2(real_gs, gs_bak)
print(f"backed up DB -> {db_bak.name}")
print(f"backed up GS -> {gs_bak.name}")

try:
    root = m.tk.Tk()
    app = m.CodexThreadManager(root)
    app.root.withdraw()  # hide window during automated test

    print("=== GUI Test 1: initial state ===")
    check("threads loaded", len(app.threads) > 0)
    check("tree has items", len(app.tree.get_children()) > 0)
    check("delete btn disabled initially", str(app.del_btn.cget("state")) == "disabled")
    check("default mode is archive", app.delete_mode.get() == "archive")
    check("codex running detected", "Codex" in app.codex_running.get())

    print("\n=== GUI Test 2: checkbox toggle via tree.set ===")
    kids = app.tree.get_children()
    if kids:
        first = kids[0]
        app.tree.set(first, "sel", "Y")
        app._upd_btn()
        check("delete btn enabled after sel", str(app.del_btn.cget("state")) == "normal")
        check("1 thread selected", len(app._get_sel()) == 1)
        # toggle off
        app.tree.set(first, "sel", "")
        app._upd_btn()
        check("delete btn disabled after deselect", str(app.del_btn.cget("state")) == "disabled")

    print("\n=== GUI Test 3: select all / toggle_all ===")
    app.toggle_all()
    n_visible = len([k for k in app.tree.get_children()])
    check("all visible selected", len(app._get_sel()) == n_visible)
    app.toggle_all()
    check("all deselected", len(app._get_sel()) == 0)

    print("\n=== GUI Test 4: search filter ===")
    app.search_var.set("codex")
    app._filter()
    visible_after = len([k for k in app.tree.get_children()])
    # some should be visible (threads mentioning codex in title)
    check("filter shows matches (>0)", visible_after > 0)
    # clear filter
    app.search_var.set("")
    app._filter()
    check("filter cleared", len([k for k in app.tree.get_children()]) >= visible_after)

    print("\n=== GUI Test 5: detail panel ===")
    kids2 = app.tree.get_children()
    if kids2:
        app.tree.selection_set(kids2[0])
        app.tree.focus(kids2[0])
        app._show_detail()
        content = app.detail.get("1.0", "end")
        check("detail non-empty", len(content.strip()) > 20)
        check("detail has Thread ID", "Thread ID" in content)

    print("\n=== GUI Test 6: switch delete modes ===")
    for mode, label, desc in app.DELETE_MODES:
        app.delete_mode.set(mode)
        check(f"mode {mode} settable", app.delete_mode.get() == mode)

    print("\n=== GUI Test 7: delete mode labels ===")
    check("has 3 modes", len(app.DELETE_MODES) == 3)
    check("archive mode", app.DELETE_MODES[0][0] == "archive")
    check("database mode", app.DELETE_MODES[1][0] == "database")
    check("full mode", app.DELETE_MODES[2][0] == "full")

    print("\n=== GUI Test 8: terminate_codex exists ===")
    check("terminate_codex callable", callable(getattr(m, "terminate_codex", None)))
    check("kill_codex callable", callable(getattr(m, "kill_codex", None)))
    check("find_codex_processes callable", callable(getattr(m, "find_codex_processes", None)))

    root.destroy()

    print(f"\n{'='*40}")
    print(f"GUI TESTS: {PASS} passed, {FAIL} failed")

finally:
    # restore real files (in case any test wrote)
    shutil.copy2(db_bak, real_db)
    shutil.copy2(gs_bak, real_gs)
    db_bak.unlink(missing_ok=True)
    gs_bak.unlink(missing_ok=True)
    print("restored real DB and GS from backup")

import sys
sys.exit(0 if FAIL == 0 else 1)



