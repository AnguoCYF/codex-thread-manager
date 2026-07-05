# Codex Thread Manager

A pure-local, GUI, zero-backend visual tool to manage OpenAI Codex desktop conversations. Scan `~/.codex`, list every thread from `state_5.sqlite`, search, inspect details, and delete with three tiers: **archive only / database delete / full wipe (4 traces)**. Includes a "Terminate Codex" button to close all Codex processes before deleting.

**Languages:** [English](README.md) | [中文](README.zh-CN.md)

---

## Features

- **Auto-scan** `~/.codex`: reads `state_5.sqlite` threads table and `.codex-global-state.json`
- **Visual list**: created time / title / thread ID / active or archived / accessible on this machine / rollout file size
- **Batch selection**: click the "Sel" column cell to toggle a row, click the column header to select/deselect all
- **Live search** filter by title or thread ID
- **Detail panel**: cwd, rollout path, outputs dir, workspace root hint
- **Three delete modes**:
  | Mode | Action | Restorable |
  |---|---|---|
  | **Archive only (soft)** | Mark `archived=1`, rollout untouched | Yes |
  | **Database delete** | Delete state_5 row + clear 5 global-state fields, rollout kept | Yes (manually) |
  | **Full wipe (4 traces)** | DB row + global state + rollout file + outputs dirs + run logs | **No** |
- **Terminate Codex**: detect and kill all Codex processes in one click (required before deleting, otherwise Codex overwrites your changes on exit)
- **Auto-backup** DB and global state to `.bak-del-*` files before destructive ops
- **5-second countdown** confirmation to prevent misclicks; extra warning if Codex is still running
- Reads/writes local files only. No network, no upload, no third-party services
- **Cross-platform**: Windows (wmic/taskkill) and Linux (pgrep/SIGTERM)

---

## Requirements

- Windows 10/11 or Linux (X11)
- Python 3.8+ with tkinter (default in official installers; on Debian/Ubuntu: `sudo apt install python3-tk`)

## Run

```powershell
python codex_thread_manager.py
```

After the GUI opens:
1. The left panel auto-loads all threads
2. Click a cell in the "Sel" column to tick rows you want to operate on
3. Pick a delete mode on the right
4. Click **Delete** → confirm dialog (5s countdown) → confirm
5. Click **Terminate Codex** before deleting for safety
6. Click **Refresh** to reload the list and see the result

---

## What Codex stores locally

Each conversation (thread) leaves 4 traces:

1. **Thread metadata** in `state_5.sqlite` `threads` table
2. **Conversation log** at `sessions/<year>/<month>/<day>/rollout-*.jsonl` (moved to `archived_sessions/` when archived)
3. **Global state** in `.codex-global-state.json`, with 5 fields referencing the thread ID:
   - `projectless-thread-ids`
   - `thread-workspace-root-hints`
   - `thread-projectless-output-directories`
   - `pinned-thread-ids`
   - `thread-writable-roots`
4. **Project directory** pointed to by `threads.cwd`; projectless threads also have an `outputs/` dir

Codex's built-in archive only flips `archived=1` and moves the rollout. "Full wipe" cleans all 4 traces.

---

## Safety

- **Terminate Codex before deleting**: Codex writes back global state on exit and will overwrite your changes if it's running
- Full-wipe auto-backs-up `state_5.sqlite` and `.codex-global-state.json` to `.bak-del-*` in the same dir (manually restorable)
- Deleting a project dir inside an OneDrive sync folder propagates the deletion to other machines via OneDrive. Confirm before deleting

---

## Tests

Three suites, none touch real data:

```powershell
python tests/test_unit.py    # 38 unit tests
python tests/test_gui.py     # 24 GUI interaction tests (window hidden)
python tests/test_e2e.py     # 15 end-to-end three-tier delete tests (temp mock CODEX_HOME)
```

Current status: **77 PASS**.

---

## Releases

Prebuilt binaries are on the [Releases page](../../releases):

- `codex-thread-manager-windows.exe` — standalone Windows executable, no Python needed
- `codex-thread-manager-linux` — standalone Linux binary (built on a Debian-based system)

## Build from source

```powershell
pip install pyinstaller
pyinstaller --onefile --windowed --name codex-thread-manager codex_thread_manager.py
```

---

## Files

| File | Purpose |
|---|---|
| `codex_thread_manager.py` | Main program, single file, no external deps |
| `tests/test_unit.py` | Unit tests (module import, functions, read-only real .codex, mock full delete) |
| `tests/test_gui.py` | GUI interaction tests (selection, search, detail, mode switch) |
| `tests/test_e2e.py` | End-to-end three-tier delete logic (temp mock, never touches real data) |
| `LICENSE` | MIT |

---

## Known behavior

- The sidebar's authoritative source is `state_5.sqlite`; `session_index.jsonl` may lag or be garbled, this tool trusts the DB
- If you use [cc-switch](https://github.com/farion1231/cc-switch)'s "Unify Codex session history" toggle, thread count changes accordingly; this tool reads live so it stays correct
- Process detection uses `wmic` on Windows (~160ms) and `pgrep` on Linux

## License

MIT
