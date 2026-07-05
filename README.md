# Codex Thread Manager

一个纯本地、可视化、零后端依赖的 **OpenAI Codex 桌面版对话管理工具**。

扫描 `~/.codex` 目录，读取 `state_5.sqlite` 中的全部对话线程，在 GUI 中列表、搜索、查看详情，并支持三档删除：**仅归档 / 数据库删除 / 完整擦除（4 处痕迹）**。提供 "Terminate Codex" 一键关闭所有 Codex 进程（删除前必须先关 Codex，否则修改会被覆盖）。

A pure-local, GUI, zero-backend visual tool to manage OpenAI Codex desktop conversations.

---

## 功能特性

- **自动扫描** `~/.codex`，读取 `state_5.sqlite` threads 表与 `.codex-global-state.json`
- **可视化列表**：创建时间 / 标题 / 线程 ID / 活跃或归档 / 本机是否可达 / rollout 文件大小
- **勾选批量操作**：点 "Sel" 列单元格切换单个勾选，点表头全选/反选
- **搜索过滤**：按标题或线程 ID 实时过滤
- **详情面板**：cwd、rollout 路径、outputs 目录、工作区根提示
- **三档删除模式**：
  | 模式 | 操作 | 可恢复 |
  |---|---|---|
  | **仅归档（软删）** | 标记 `archived=1`，rollout 不动 | 是 |
  | **数据库删除** | 删 state_5 行 + 清全局状态 5 字段，rollout 保留 | 是（手动恢复） |
  | **完整擦除（4 处痕迹）** | DB 行 + 全局状态 + rollout 文件 + outputs 目录 + 运行日志 | **否** |
- **Terminate Codex**：一键检测并终止全部 Codex 进程（删除前的安全步骤）
- **删除前自动备份** DB 与全局状态到同目录 `.bak-del-*` 文件
- **5 秒倒计时确认**，避免误触；若检测到 Codex 仍运行会额外警告
- 全程**读写本机文件**，不联网、不上传、不依赖任何第三方服务

---

## 快速开始

### 环境要求

- Windows 10/11
- Python 3.8+（需包含 tkinter，官方安装包默认勾选即可）

### 运行

```powershell
python codex_thread_manager.py
```

弹出 GUI 后：
1. 左侧列表自动加载全部线程
2. 点 "Sel" 列单元格勾选要操作的线程
3. 右侧选择删除模式
4. 点 **Delete** → 确认对话框（5 秒倒计时）→ 确认
5. 点 **Terminate Codex** 先关闭 Codex，再删除更安全
6. 点 **Refresh** 重新加载列表查看效果

---

## Codex 在本机存了什么

每个对话（thread）由 4 处痕迹共同构成：

1. **线程元数据库** `state_5.sqlite` `threads` 表
2. **对话内容日志** `sessions/<年>/<月>/<日>/rollout-*.jsonl`（归档后移到 `archived_sessions/`）
3. **全局状态** `.codex-global-state.json`，含 5 个引用该线程 ID 的字段：
   - `projectless-thread-ids`
   - `thread-workspace-root-hints`
   - `thread-projectless-output-directories`
   - `pinned-thread-ids`
   - `thread-writable-roots`
4. **项目目录** threads.cwd 指向的代码/文档，projectless 线程还有 `outputs/` 目录

Codex 自带的归档只做 `archived=1` + 移动 rollout 文件，不做物理删除。"完整擦除" 模式清理以上 4 处全部痕迹。

---

## 安全建议

- **删除前先 Terminate Codex**：Codex 退出时会写回全局状态，若你在运行中删除，覆盖会丢掉你的修改
- 完整擦除前会自动备份 `state_5.sqlite` 与 `.codex-global-state.json` 到同目录 `.bak-del-*` 文件，仍可手动恢复
- OneDrive 同步盘内的项目目录删除会被 OneDrive 同步到其他机器，删前请确认

---

## 测试

项目附带三套测试，全部不碰真实数据：

```powershell
python tests\test_unit.py   # 38 项单元测试
python tests\test_gui.py    # 24 项 GUI 交互测试（自动隐藏窗口）
python tests\test_e2e.py    # 15 项三档删除端到端测试（临时 mock CODEX_HOME）
```

当前状态：**77 项全 PASS**。

---

## 文件说明

| 文件 | 说明 |
|---|---|
| `codex_thread_manager.py` | 主程序，单文件，无外部依赖 |
| `tests/test_unit.py` | 单元测试（模块导入、函数、真实 .codex 只读校验） |
| `tests/test_gui.py` | GUI 交互测试（勾选、搜索、详情、模式切换） |
| `tests/test_e2e.py` | 端到端三档删除逻辑测试（临时 mock，不碰真实数据） |
| `LICENSE` | MIT |

---

## 路径与进程检测说明

- 进程检测用 `wmic process where "name like '%odex%'"`，约 160ms 返回，兼容多 Codex 进程
- 路径自动归一化 `\\?\` 前缀，兼容 Windows 长路径

---

## 已知行为

- 侧边栏线程列表的权威来源是 `state_5.sqlite`，`session_index.jsonl` 可能滞后或乱码，本工具以数据库为准
- 若你使用 [cc-switch](https://github.com/farion1231/cc-switch) 的 "统一 Codex 会话历史" 功能，线程数会随之变化，本工具实时读取所以无影响

---

## License

MIT
