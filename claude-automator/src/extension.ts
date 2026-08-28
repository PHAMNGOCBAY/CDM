import * as vscode from 'vscode';

// ── Constants ────────────────────────────────────────────────────────────────

const EXT_ID = 'claudeAutomator';
const CLAUDE_EXT_ID = 'anthropic.claude-code';

/** The VS Code configuration section owned by Claude Code */
const CLAUDE_SECTION = 'claudeCode';

/** Settings toggled when auto-approve is switched ON */
const SETTINGS_ON: Record<string, unknown> = {
  initialPermissionMode: 'bypassPermissions',
  allowDangerouslySkipPermissions: true,
};

/** Settings restored when auto-approve is switched OFF */
const SETTINGS_OFF: Record<string, unknown> = {
  initialPermissionMode: 'default',
  allowDangerouslySkipPermissions: false,
};

// ── Status-bar item ──────────────────────────────────────────────────────────

let statusBarItem: vscode.StatusBarItem;

function updateStatusBar(enabled: boolean): void {
  if (enabled) {
    statusBarItem.text = '$(zap) Claude Auto: ON';
    statusBarItem.tooltip = 'Claude Code auto-approve is ENABLED – click to disable';
    statusBarItem.backgroundColor = new vscode.ThemeColor(
      'statusBarItem.warningBackground'
    );
    statusBarItem.color = new vscode.ThemeColor('statusBarItem.warningForeground');
  } else {
    statusBarItem.text = '$(shield) Claude Auto: OFF';
    statusBarItem.tooltip = 'Claude Code auto-approve is DISABLED – click to enable';
    statusBarItem.backgroundColor = undefined;
    statusBarItem.color = undefined;
  }
  statusBarItem.show();
}

// ── Helpers ──────────────────────────────────────────────────────────────────

function isClaudeCodeInstalled(): boolean {
  return vscode.extensions.getExtension(CLAUDE_EXT_ID) !== undefined;
}

async function applyClaudeSettings(
  settings: Record<string, unknown>,
  target: vscode.ConfigurationTarget
): Promise<void> {
  const config = vscode.workspace.getConfiguration(CLAUDE_SECTION);
  for (const [key, value] of Object.entries(settings)) {
    await config.update(key, value, target);
  }
}

// ── Toggle logic ─────────────────────────────────────────────────────────────

async function toggleAutoApprove(context: vscode.ExtensionContext): Promise<void> {
  // Read current state from our own config (persisted across sessions)
  const ourConfig = vscode.workspace.getConfiguration(EXT_ID);
  const currentlyEnabled: boolean = ourConfig.get<boolean>('enabled', false);
  const nextEnabled = !currentlyEnabled;

  // Warn the user before enabling dangerous settings
  if (nextEnabled) {
    if (!isClaudeCodeInstalled()) {
      const choice = await vscode.window.showWarningMessage(
        'Claude Code extension does not appear to be installed. Continue anyway?',
        { modal: true },
        'Continue',
        'Cancel'
      );
      if (choice !== 'Continue') {
        return;
      }
    }

    const confirm = await vscode.window.showWarningMessage(
      '⚠️  Enabling auto-approve lets Claude execute ANY command (including bash) without asking. Are you sure?',
      { modal: true },
      'Enable Auto-Approve',
      'Cancel'
    );
    if (confirm !== 'Enable Auto-Approve') {
      return;
    }
  }

  // Apply Claude Code settings at the Global scope so they affect all workspaces
  const target = vscode.ConfigurationTarget.Global;
  try {
    await applyClaudeSettings(nextEnabled ? SETTINGS_ON : SETTINGS_OFF, target);
  } catch (err) {
    vscode.window.showErrorMessage(
      `Claude Automator: Failed to update settings – ${String(err)}`
    );
    return;
  }

  // Persist our own toggle state
  await ourConfig.update('enabled', nextEnabled, vscode.ConfigurationTarget.Global);

  // Refresh the status bar
  updateStatusBar(nextEnabled);

  // Notify the user
  if (nextEnabled) {
    vscode.window.showWarningMessage(
      '⚡ Claude Auto-Approve is now ON. Claude Code will bypass all permission prompts.'
    );
  } else {
    vscode.window.showInformationMessage(
      '🛡️ Claude Auto-Approve is now OFF. Normal permission prompts restored.'
    );
  }
}

// ── Extension lifecycle ──────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext): void {
  // Create the status bar button (right-aligned, high priority to keep it visible)
  statusBarItem = vscode.window.createStatusBarItem(
    vscode.StatusBarAlignment.Right,
    100
  );
  statusBarItem.command = 'claudeAutomator.toggleAutoApprove';
  context.subscriptions.push(statusBarItem);

  // Initialise the status bar from the persisted config value
  const enabled = vscode.workspace
    .getConfiguration(EXT_ID)
    .get<boolean>('enabled', false);
  updateStatusBar(enabled);

  // Register the toggle command
  const disposable = vscode.commands.registerCommand(
    'claudeAutomator.toggleAutoApprove',
    () => toggleAutoApprove(context)
  );
  context.subscriptions.push(disposable);

  // React to external config changes (e.g. settings.json edits)
  context.subscriptions.push(
    vscode.workspace.onDidChangeConfiguration((e) => {
      if (e.affectsConfiguration(`${EXT_ID}.enabled`)) {
        const newEnabled = vscode.workspace
          .getConfiguration(EXT_ID)
          .get<boolean>('enabled', false);
        updateStatusBar(newEnabled);
      }
    })
  );
}

export function deactivate(): void {
  // VS Code disposes subscriptions automatically; nothing extra needed.
}
