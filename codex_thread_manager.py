#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Codex Thread Manager - visual conversation management tool.

Auto-scans ~/.codex, lists all threads, supports 3-tier deletion:
  archive only / database delete / full wipe (4 traces).
With GUI: refresh, restart Codex, inspect results.

Usage: python codex_thread_manager.py
Requires: Python 3.8+, tkinter (built-in)
"""
import os, sys, json, shutil, sqlite3, datetime, subprocess, time, platform
from pathlib import Path
try:
    import tkinter as tk
    from tkinter import ttk, messagebox, scrolledtext
except ImportError:
    print("ERROR: tkinter not available"); sys.exit(1)

HOME = Path.home()
CODEX_HOME = HOME / ".codex"
STATE_DB = CODEX_HOME / "state_5.sqlite"
GLOBAL_STATE = CODEX_HOME / ".codex-global-state.json"
LOGS_DB = CODEX_HOME / "logs_2.sqlite"
GS_TID_FIELDS = [("projectless-thread-ids","list"),("thread-workspace-root-hints","dict"),("thread-projectless-output-directories","dict"),("pinned-thread-ids","list"),("thread-writable-roots","dict")]
TZ = datetime.timezone(datetime.timedelta(hours=8))

def fmt_ts(ts):
    if not ts: return ""
    try: return datetime.datetime.fromtimestamp(int(ts),TZ).strftime("%Y-%m-%d %H:%M")
    except: return str(ts)

def norm_path(p):
    if not p: return ""
    return p.replace("\\\\?\\","")

def fmt_size(n):
    if not n: return "-"
    n=float(n)
    for u in ["B","KB","MB","GB"]:
        if n<1024 or u=="GB": return f"{n:.1f} {u}"
        n/=1024

def backup_file(src, tag="mgr"):
    if not src.exists(): return None
    ts=datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    dst=src.parent / f"{src.name}.bak-{tag}-{ts}"
    shutil.copy2(src,dst); return dst

def load_threads_from_db():
    if not STATE_DB.exists(): return [], "state_5.sqlite not found"
    try:
        con=sqlite3.connect(str(STATE_DB)); con.row_factory=sqlite3.Row
        rows=con.execute("SELECT id,rollout_path,created_at,updated_at,cwd,title,archived,archived_at FROM threads ORDER BY created_at DESC").fetchall()
        con.close(); return [dict(r) for r in rows], None
    except Exception as e: return [], f"DB read error: {e}"

def load_global_state():
    if not GLOBAL_STATE.exists(): return {}, None
    try:
        with open(GLOBAL_STATE,"r",encoding="utf-8") as f: return json.load(f), None
    except Exception as e: return {}, f"Global state read error: {e}"

def save_global_state(d):
    with open(GLOBAL_STATE,"w",encoding="utf-8") as f: json.dump(d,f,ensure_ascii=False,indent=2)

def remove_tid_from_gs(gs, tid):
    c=0
    for field,ftype in GS_TID_FIELDS:
        if field not in gs: continue
        if ftype=="list" and tid in gs[field]:
            gs[field]=[x for x in gs[field] if x!=tid]; c+=1
        elif ftype=="dict" and tid in gs[field]:
            del gs[field][tid]; c+=1
    return gs, c

def get_rollout_size(p):
    p=norm_path(p)
    if not p or not os.path.exists(p): return 0
    try: return os.path.getsize(p)
    except: return 0

def find_codex_processes():
    """Detect running Codex processes. Cross-platform: Windows uses wmic, Linux uses pgrep."""
    if platform.system()=="Windows":
        try:
            out=subprocess.run(["wmic","process","where","name like '%odex%'","get","ProcessId,Name","/format:csv"],capture_output=True,text=True,timeout=15).stdout
        except Exception: return []
        procs=[]
        for line in out.strip().splitlines():
            line=line.strip()
            if not line or "Node," in line: continue
            parts=[p.strip() for p in line.split(",")]
            if len(parts)<3: continue
            name=parts[1]; pid_s=parts[2]
            if "codex" not in name.lower(): continue
            try: pid=int(pid_s)
            except: continue
            procs.append((pid,name))
        return procs
    else:
        try:
            out=subprocess.run(["pgrep","-a","-f","codex"],capture_output=True,text=True,timeout=10).stdout
        except Exception: return []
        procs=[]
        for line in out.strip().splitlines():
            line=line.strip()
            if not line: continue
            parts=line.split(None,1)
            if len(parts)<2: continue
            try: pid=int(parts[0])
            except: continue
            name=parts[1].split()[0] if parts[1].split() else parts[1]
            if "codex" not in name.lower(): continue
            procs.append((pid,name))
        return procs


def kill_codex():
    procs=find_codex_processes()
    if not procs: return False,"No running Codex process found"
    k=0
    for pid,name in procs:
        try:
            if platform.system()=="Windows":
                subprocess.run(["taskkill","/F","/PID",str(pid)],capture_output=True,timeout=10)
            else:
                import signal
                os.kill(pid, signal.SIGTERM)
            k+=1
        except Exception: pass
    return True, f"Terminated {k}/{len(procs)} Codex processes"

def find_codex_exe():
    """Locate Codex executable (Windows only; Linux users relaunch manually)."""
    if platform.system()!="Windows": return None
    try:
        out=subprocess.run(["wmic","process","where","name='Codex.exe'","get","ExecutablePath"],capture_output=True,text=True,timeout=10).stdout
        for line in out.strip().splitlines():
            line=line.strip()
            if line.endswith("Codex.exe") and "WindowsApps" in line: return line
    except Exception: pass
    return None

def terminate_codex(parent):
    if not messagebox.askyesno("Terminate Codex","Terminate all running Codex processes?\n\nUse this before deleting, then relaunch Codex manually afterwards."): return
    ok,msg=kill_codex(); parent.status.set(msg); parent.update_idletasks()
    if ok: time.sleep(1)
    procs=find_codex_processes()
    if procs: parent.status.set(f"Terminated, but {len(procs)} still running - close manually")
    else: parent.status.set("Codex fully terminated. Relaunch manually when ready.")

def kill_codex():
    procs=find_codex_processes()
    if not procs: return False,"No running Codex process found"
    k=0
    for pid,name in procs:
        try: subprocess.run(["taskkill","/F","/PID",str(pid)],capture_output=True,timeout=10); k+=1
        except: pass
    return True, f"Terminated {k}/{len(procs)} Codex processes"

def find_codex_exe():
    try:
        out=subprocess.run(["wmic","process","where","name='Codex.exe'","get","ExecutablePath"],capture_output=True,text=True,timeout=10).stdout
        for line in out.strip().splitlines():
            line=line.strip()
            if line.endswith("Codex.exe") and "WindowsApps" in line: return line
    except: pass
    return None

def terminate_codex(parent):
    if not messagebox.askyesno("Terminate Codex","Terminate all running Codex processes?\\n\\nUse this before deleting, then relaunch Codex manually afterwards."): return
    ok,msg=kill_codex(); parent.status.set(msg); parent.update_idletasks()
    if ok: time.sleep(1)
    procs=find_codex_processes()
    if procs: parent.status.set(f"Terminated, but {len(procs)} still running - close manually")
    else: parent.status.set("Codex fully terminated. Relaunch manually when ready.")
class ConfirmDialog(tk.Toplevel):
    def __init__(self, parent, title, lines, total_size=None):
        super().__init__(parent); self.title(title); self.result=False
        self.countdown=5; self.resizable(True,True); self.transient(parent); self.grab_set()
        frm=ttk.Frame(self,padding=15); frm.pack(fill="both",expand=True)
        ttk.Label(frm,text="The following will be operated on, action is irreversible:",font=("",10,"bold")).pack(anchor="w",pady=(0,8))
        txt=scrolledtext.ScrolledText(frm,width=80,height=12,wrap="word"); txt.pack(fill="both",expand=True,pady=4)
        for l in lines: txt.insert("end",l+"\n")
        txt.config(state="disabled")
        if total_size: ttk.Label(frm,text=f"Space to free: ~ {fmt_size(total_size)}",font=("",9,"bold")).pack(anchor="w",pady=(4,0))
        ttk.Label(frm,text="Please close Codex first, otherwise changes will be overwritten!",foreground="red").pack(anchor="w",pady=(8,4))
        self.cl=ttk.Label(frm,text=f"Confirm button available in {self.countdown} seconds",foreground="gray"); self.cl.pack(anchor="w")
        bf=ttk.Frame(frm); bf.pack(fill="x",pady=(10,0))
        self.cb=ttk.Button(bf,text="Confirm",state="disabled",command=self.on_ok); self.cb.pack(side="right",padx=(8,0))
        ttk.Button(bf,text="Cancel",command=self.on_cancel).pack(side="right")
        self.after(1000,self._tick); self.geometry("620x420"); self.protocol("WM_DELETE_WINDOW",self.on_cancel)
    def _tick(self):
        self.countdown-=1
        if self.countdown<=0: self.cl.config(text="Ready to confirm",foreground="green"); self.cb.config(state="normal")
        else: self.cl.config(text=f"Confirm button available in {self.countdown} seconds"); self.after(1000,self._tick)
    def on_ok(self): self.result=True; self.destroy()
    def on_cancel(self): self.result=False; self.destroy()


class CodexThreadManager:
    DELETE_MODES=[("archive","Archive only (soft)","Mark archived=1, rollout kept, sidebar hidden but restorable, no files deleted"),
                  ("database","Database delete","Delete state_5 row + clear 5 global-state fields, rollout file kept restorable"),
                  ("full","Full wipe (4 traces)","DB row + global state + rollout + outputs dirs + run logs, irreversible")]
    def __init__(self,root):
        self.root=root; root.title("Codex Thread Manager"); root.geometry("1100x700")
        self.threads=[]; self.global_state={}
        self.delete_mode=tk.StringVar(value="archive"); self.search_var=tk.StringVar()
        self.status=tk.StringVar(value="Ready"); self.codex_running=tk.StringVar(value="")
        self._build_ui(); self.refresh()
    def _build_ui(self):
        top=ttk.Frame(self.root,padding=8); top.pack(fill="x")
        ttk.Button(top,text="Refresh",command=self.refresh).pack(side="left",padx=(0,4))
        ttk.Button(top,text="Terminate Codex",command=lambda:terminate_codex(self)).pack(side="left",padx=4)
        ttk.Separator(top,orient="vertical").pack(side="left",fill="y",padx=8)
        ttk.Label(top,text="Search:").pack(side="left")
        e=ttk.Entry(top,textvariable=self.search_var,width=25); e.pack(side="left",padx=(0,8)); e.bind("<KeyRelease>",lambda ev:self._filter())
        ttk.Label(top,textvariable=self.codex_running,foreground="orange").pack(side="left",padx=8)
        main=ttk.Frame(self.root,padding=(8,0)); main.pack(fill="both",expand=True)
        left=ttk.Frame(main); left.pack(fill="both",expand=True,side="left")
        ttk.Label(left,text="Thread List",font=("",10,"bold")).pack(anchor="w")
        cols=("sel","created","title","tid","arch","acc","size")
        self.tree=ttk.Treeview(left,columns=cols,show="headings",height=18)
        self.tree.heading("sel",text="Sel"); self.tree.heading("created",text="Created"); self.tree.heading("title",text="Title")
        self.tree.heading("tid",text="Thread ID"); self.tree.heading("arch",text="Status"); self.tree.heading("acc",text="Access"); self.tree.heading("size",text="Rollout")
        self.tree.column("sel",width=36,stretch=False,anchor="center"); self.tree.column("created",width=120,stretch=False)
        self.tree.column("title",width=320); self.tree.column("tid",width=200,stretch=False)
        self.tree.column("arch",width=70,stretch=False,anchor="center"); self.tree.column("acc",width=70,stretch=False,anchor="center"); self.tree.column("size",width=90,stretch=False,anchor="e")
        self.tree.pack(fill="both",expand=True,side="top")
        self.tree.bind("<<TreeviewSelect>>",self._on_sel); self.tree.bind("<Button-1>",self._on_click)
        sb=ttk.Scrollbar(left,orient="vertical",command=self.tree.yview); self.tree.configure(yscrollcommand=sb.set); sb.pack(side="right",fill="y")
        right=ttk.Frame(main,width=400); right.pack(fill="both",side="right",padx=(8,0)); right.pack_propagate(False)
        ttk.Label(right,text="Thread Details",font=("",10,"bold")).pack(anchor="w")
        self.detail=scrolledtext.ScrolledText(right,width=48,height=20,wrap="word",font=("Consolas",9)); self.detail.pack(fill="both",expand=True,pady=4)
        mf=ttk.LabelFrame(right,text="Delete Mode",padding=8); mf.pack(fill="x",pady=(8,0))
        for v,l,d in self.DELETE_MODES:
            ttk.Radiobutton(mf,text=l,value=v,variable=self.delete_mode).pack(anchor="w")
            ttk.Label(mf,text=d,font=("",8),foreground="gray",wraplength=360).pack(anchor="w",padx=(16,0),pady=(0,4))
        of=ttk.Frame(right); of.pack(fill="x",pady=(8,0))
        self.del_btn=ttk.Button(of,text="Delete",command=self.do_delete,state="disabled"); self.del_btn.pack(side="right")
        ttk.Button(of,text="Select All",command=self.toggle_all).pack(side="right",padx=(0,4))
        bar=ttk.Frame(self.root,padding=(8,4)); bar.pack(side="bottom",fill="x")
        ttk.Label(bar,textvariable=self.status,font=("",8)).pack(side="left")
    def refresh(self):
        self.threads,err=load_threads_from_db()
        if err: self.status.set(f"Error: {err}"); return
        self.global_state,err2=load_global_state()
        if err2: self.status.set(f"Warning: {err2}")
        procs=find_codex_processes()
        self.codex_running.set(f"Codex running ({len(procs)}) - close before delete!" if procs else "Codex not running")
        self._populate(); self.status.set(f"Loaded {len(self.threads)} threads")
    def _populate(self):
        for i in self.tree.get_children(): self.tree.delete(i)
        for t in self.threads:
            cwd=norm_path(t.get("cwd","")); acc="Yes" if (cwd and os.path.exists(cwd)) else "-"
            arch="Archived" if t.get("archived") else "Active"
            rp=norm_path(t.get("rollout_path","")); sz=get_rollout_size(rp)
            title=(t.get("title") or "").strip().split("\n")[0][:50] or "(no title)"
            self.tree.insert("","end",values=("",fmt_ts(t.get("created_at")),title,t.get("id",""),arch,acc,fmt_size(sz)))
        self._filter()
    def _filter(self):
        q=self.search_var.get().strip().lower()
        for i in list(self.tree.get_children()):
            if not q or q in " ".join(str(v) for v in self.tree.item(i,"values")).lower(): self.tree.reattach(i,"","end")
            else: self.tree.detach(i)
    def _on_click(self,e):
        region=self.tree.identify("region",e.x,e.y)
        col=self.tree.identify_column(e.x)
        if region=="heading" and col=="#1":
            self.toggle_all(); return "break"
        if region=="cell" and col=="#1":
            row=self.tree.identify_row(e.y)
            if row:
                cur=self.tree.set(row,"sel")
                self.tree.set(row,"sel","" if cur=="Y" else "Y")
                self.tree.selection_set(row); self.tree.focus(row)
                self._upd_btn(); self._show_detail()
            return "break"
    def toggle_all(self):
        ch=self.tree.get_children()
        if not ch: return
        all_on=all(self.tree.set(c,"sel")=="Y" for c in ch)
        for c in ch: self.tree.set(c,"sel","" if all_on else "Y")
        self._upd_btn()
    def _on_sel(self,e=None):
        self._upd_btn(); self._show_detail()
    def _upd_btn(self):
        self.del_btn.config(state="normal" if self._get_sel() else "disabled")
    def _get_sel(self):
        return [self.tree.item(i,"values")[3] for i in self.tree.get_children() if self.tree.set(i,"sel")=="Y"]
    def _show_detail(self):
        s=self.tree.selection()
        if not s: return
        tid=self.tree.item(s[0],"values")[3]
        t=next((x for x in self.threads if x.get("id")==tid),None)
        if not t: return
        self.detail.config(state="normal"); self.detail.delete("1.0","end")
        L=[f"Thread ID: {t.get('id','')}",f"Title: {(t.get('title') or '').strip()[:120]}",
           f"Created: {fmt_ts(t.get('created_at'))}",f"Updated: {fmt_ts(t.get('updated_at'))}",
           f"Status: {'Archived' if t.get('archived') else 'Active'}","",
           f"Working dir (cwd):",f"  {norm_path(t.get('cwd',''))}",
           f"  Exists on this machine: {'Yes' if os.path.exists(norm_path(t.get('cwd',''))) else 'No'}","",
           f"Rollout file:",f"  {norm_path(t.get('rollout_path',''))}",
           f"  Exists: {'Yes' if os.path.exists(norm_path(t.get('rollout_path',''))) else 'No'}, Size: {fmt_size(get_rollout_size(t.get('rollout_path','')))}",""]
        om=self.global_state.get("thread-projectless-output-directories",{})
        od=om.get(tid,"")
        if od: L+= [f"Outputs dir:",f"  {od}",f"  Exists: {'Yes' if os.path.exists(od) else 'No'}",""]
        hints=self.global_state.get("thread-workspace-root-hints",{})
        h=hints.get(tid,"")
        if h: L.append(f"Workspace root hint: {h}")
        self.detail.insert("1.0","\n".join(L)); self.detail.config(state="disabled")
    def do_delete(self):
        tids=self._get_sel()
        if not tids: return
        mode=self.delete_mode.get(); ml=dict((m[0],m[1]) for m in self.DELETE_MODES)[mode]
        S=[]; ts=0
        for tid in tids:
            t=next((x for x in self.threads if x.get("id")==tid),None)
            if not t: continue
            S.append(f"- [{tid[:8]}] {(t.get('title') or '').strip()[:50]}")
            rp=norm_path(t.get("rollout_path","")); s=get_rollout_size(rp); ts+=s
            if mode=="archive": S.append("    Action: mark archived=1")
            elif mode=="database": S.append("    Action: delete DB row + clear 5 global-state fields"); S.append(f"    Rollout kept: {rp}")
            elif mode=="full":
                S.append("    Action: DELETE DB row"); S.append(f"    Delete rollout: {rp} ({fmt_size(s)})")
                om=self.global_state.get("thread-projectless-output-directories",{})
                od=om.get(tid,"")
                if od and os.path.exists(od):
                    try:
                        ds=sum(os.path.getsize(os.path.join(d,f)) for d,_,fs in os.walk(od) for f in fs)
                        S.append(f"    Delete outputs: {od} ({fmt_size(ds)})"); ts+=ds
                    except: S.append(f"    Delete outputs: {od} (size unknown)")
                S.append("    Clear run logs for this thread in logs_2")
        procs=find_codex_processes()
        if procs: S=["",f"!! WARNING: Codex running ({len(procs)} processes) !!","Changes may be overwritten on Codex exit, close Codex first",""]+S
        S=[f"Delete mode: {ml}",f"Selected {len(tids)} threads:",""]+S
        dlg=ConfirmDialog(self.root,"Confirm Delete",S,ts if mode=="full" else None)
        self.root.wait_window(dlg)
        if not dlg.result: self.status.set("Cancelled"); return
        if procs and not messagebox.askyesno("Codex Running","Codex is still running, changes may be overwritten.\n\nContinue anyway?"): self.status.set("Cancelled"); return
        self.status.set("Deleting..."); self.root.update_idletasks()
        r=self._exec_delete(tids,mode); self.status.set(r); self.refresh()
    def _exec_delete(self,tids,mode):
        log=[]; dr=0; gs=0; df=0; dd=0; dl=0
        # snapshot outputs paths BEFORE global state gets cleared
        out_paths={}
        if mode=="full":
            om=self.global_state.get("thread-projectless-output-directories",{})
            for tid in tids:
                p=om.get(tid,"")
                if p: out_paths[tid]=p
        if mode in ("database","full"):
            bk=backup_file(STATE_DB,"del")
            if bk: log.append(f"Backed up DB: {bk.name}")
        if mode=="full":
            bk2=backup_file(GLOBAL_STATE,"del")
            if bk2: log.append(f"Backed up global state: {bk2.name}")
        if mode=="archive":
            try:
                con=sqlite3.connect(str(STATE_DB))
                for tid in tids:
                    con.execute("UPDATE threads SET archived=1,archived_at=? WHERE id=?",(int(datetime.datetime.now(TZ).timestamp()),tid)); dr+=1
                con.commit(); con.close()
            except Exception as e: return f"Archive failed: {e}"
            return f"Archived {dr} threads (soft delete, restorable)"
        if mode in ("database","full"):
            try:
                con=sqlite3.connect(str(STATE_DB))
                for tid in tids:
                    c=con.execute("DELETE FROM threads WHERE id=?",(tid,)); dr+=c.rowcount
                con.commit(); con.close()
            except Exception as e: log.append(f"DB row delete failed: {e}")
            try:
                g=self.global_state
                for tid in tids: g,c=remove_tid_from_gs(g,tid); gs+=c
                save_global_state(g)
            except Exception as e: log.append(f"Global state clear failed: {e}")
        if mode=="full":
            for tid in tids:
                t=next((x for x in self.threads if x.get("id")==tid),None)
                if not t: continue
                rp=norm_path(t.get("rollout_path",""))
                if rp and os.path.exists(rp):
                    try: os.remove(rp); df+=1
                    except Exception as e: log.append(f"Rollout delete failed {tid[:8]}: {e}")
                od=out_paths.get(tid,"")
                if od and os.path.exists(od):
                    try: shutil.rmtree(od); dd+=1
                    except Exception as e: log.append(f"Outputs delete failed {tid[:8]}: {e}")
            if LOGS_DB.exists():
                try:
                    con=sqlite3.connect(str(LOGS_DB))
                    ph=",".join("?"*len(tids))
                    c=con.execute(f"DELETE FROM logs WHERE thread_id IN ({ph})",tids); dl=c.rowcount; con.commit(); con.close()
                except Exception as e: log.append(f"Log cleanup failed: {e}")
        parts=[f"DB rows {dr}",f"Global state {gs} fields"]
        if mode=="full": parts+=[f"Rollout files {df}",f"Outputs dirs {dd}",f"Run logs {dl}"]
        if log: parts.append(" ; ".join(log))
        return " , ".join(parts)
if __name__=="__main__": main()
