# Codex Thread Manager v1.0

A visual GUI tool to manage, archive, and fully delete OpenAI Codex desktop thread/conversation history locally.

## Downloads

- `codex-thread-manager-windows.exe` — standalone Windows executable (no Python needed, 9.2 MB)
- `codex-thread-manager-linux` — standalone Linux binary (auto-built by GitHub Actions, appears here shortly after release)

## Quick start

1. Download the binary for your OS
2. Windows: double-click the `.exe`; Linux: `chmod +x codex-thread-manager-linux && ./codex-thread-manager-linux`
3. Select threads, pick a delete mode, confirm

## Three delete modes

| Mode | Action | Restorable |
|---|---|---|
| Archive only | Mark archived=1 | Yes |
| Database delete | Delete DB row + clear 5 global-state fields, rollout kept | Yes (manually) |
| Full wipe | DB row + global state + rollout + outputs + logs | **No** |

## Safety

- Terminate Codex before deleting (Codex overwrites state on exit)
- Auto-backups DB and global state before destructive ops
- 5-second countdown confirmation

Source code and docs: https://github.com/AnguoCYF/codex-thread-manager
