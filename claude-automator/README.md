# Claude Automator — VS Code Extension

A lightweight VS Code extension that **toggles auto-approval for Claude Code** actions with a single click.

## Features

- **Toggle Auto-Approve** – Switches between:
  - `OFF` (default) – Claude Code will ask for permission before each action
  - `ON` – Claude Code bypasses all permission prompts (uses `bypassPermissions` mode)
- **Status Bar Indicator** – Always visible in the bottom-right corner:
  - `🛡️ Claude Auto: OFF` – safe mode, normal colours
  - `⚡ Claude Auto: ON` – warning background colour to signal the active risk
- **Safety Confirmation** – Requires explicit modal confirmation before enabling
- **Persistent State** – Remembers your choice across VS Code restarts

## Usage

### Command Palette

1. Press `Ctrl+Shift+P` (Windows/Linux) or `Cmd+Shift+P` (macOS)
2. Run **Claude Automator: Toggle Auto-Approve**

### Status Bar

Click the **`Claude Auto: OFF`** / **`Claude Auto: ON`** button in the bottom-right status bar.

## Installation

### From VSIX (local build)

```bash
cd claude-automator
npm install
npm run compile
npm run package          # produces claude-automator-1.0.0.vsix
code --install-extension claude-automator-1.0.0.vsix
```

### Development mode

Open the `claude-automator` folder in VS Code and press **F5** to launch an Extension Development Host.

## Settings Changed

| Setting | OFF (default) | ON |
|---|---|---|
| `claudeCode.initialPermissionMode` | `"default"` | `"bypassPermissions"` |
| `claudeCode.allowDangerouslySkipPermissions` | `false` | `true` |

> [!WARNING]
> Enabling auto-approval lets Claude execute **any command** (including bash) without asking. Only enable this in trusted environments.

## Requirements

- VS Code 1.85+
- [Claude Code](https://marketplace.visualstudio.com/items?itemName=anthropic.claude-code) extension installed

## License

MIT
