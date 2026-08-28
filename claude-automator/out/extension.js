"use strict";
var __createBinding = (this && this.__createBinding) || (Object.create ? (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    var desc = Object.getOwnPropertyDescriptor(m, k);
    if (!desc || ("get" in desc ? !m.__esModule : desc.writable || desc.configurable)) {
      desc = { enumerable: true, get: function() { return m[k]; } };
    }
    Object.defineProperty(o, k2, desc);
}) : (function(o, m, k, k2) {
    if (k2 === undefined) k2 = k;
    o[k2] = m[k];
}));
var __setModuleDefault = (this && this.__setModuleDefault) || (Object.create ? (function(o, v) {
    Object.defineProperty(o, "default", { enumerable: true, value: v });
}) : function(o, v) {
    o["default"] = v;
});
var __importStar = (this && this.__importStar) || (function () {
    var ownKeys = function(o) {
        ownKeys = Object.getOwnPropertyNames || function (o) {
            var ar = [];
            for (var k in o) if (Object.prototype.hasOwnProperty.call(o, k)) ar[ar.length] = k;
            return ar;
        };
        return ownKeys(o);
    };
    return function (mod) {
        if (mod && mod.__esModule) return mod;
        var result = {};
        if (mod != null) for (var k = ownKeys(mod), i = 0; i < k.length; i++) if (k[i] !== "default") __createBinding(result, mod, k[i]);
        __setModuleDefault(result, mod);
        return result;
    };
})();
Object.defineProperty(exports, "__esModule", { value: true });
exports.activate = activate;
exports.deactivate = deactivate;
const vscode = __importStar(require("vscode"));
// ── Constants ────────────────────────────────────────────────────────────────
const EXT_ID = 'claudeAutomator';
const CLAUDE_EXT_ID = 'anthropic.claude-code';
/** The VS Code configuration section owned by Claude Code */
const CLAUDE_SECTION = 'claudeCode';
/** Settings toggled when auto-approve is switched ON */
const SETTINGS_ON = {
    initialPermissionMode: 'bypassPermissions',
    allowDangerouslySkipPermissions: true,
};
/** Settings restored when auto-approve is switched OFF */
const SETTINGS_OFF = {
    initialPermissionMode: 'default',
    allowDangerouslySkipPermissions: false,
};
// ── Status-bar item ──────────────────────────────────────────────────────────
let statusBarItem;
function updateStatusBar(enabled) {
    if (enabled) {
        statusBarItem.text = '$(zap) Claude Auto: ON';
        statusBarItem.tooltip = 'Claude Code auto-approve is ENABLED – click to disable';
        statusBarItem.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
        statusBarItem.color = new vscode.ThemeColor('statusBarItem.warningForeground');
    }
    else {
        statusBarItem.text = '$(shield) Claude Auto: OFF';
        statusBarItem.tooltip = 'Claude Code auto-approve is DISABLED – click to enable';
        statusBarItem.backgroundColor = undefined;
        statusBarItem.color = undefined;
    }
    statusBarItem.show();
}
// ── Helpers ──────────────────────────────────────────────────────────────────
function isClaudeCodeInstalled() {
    return vscode.extensions.getExtension(CLAUDE_EXT_ID) !== undefined;
}
async function applyClaudeSettings(settings, target) {
    const config = vscode.workspace.getConfiguration(CLAUDE_SECTION);
    for (const [key, value] of Object.entries(settings)) {
        await config.update(key, value, target);
    }
}
// ── Toggle logic ─────────────────────────────────────────────────────────────
async function toggleAutoApprove(context) {
    // Read current state from our own config (persisted across sessions)
    const ourConfig = vscode.workspace.getConfiguration(EXT_ID);
    const currentlyEnabled = ourConfig.get('enabled', false);
    const nextEnabled = !currentlyEnabled;
    // Warn the user before enabling dangerous settings
    if (nextEnabled) {
        if (!isClaudeCodeInstalled()) {
            const choice = await vscode.window.showWarningMessage('Claude Code extension does not appear to be installed. Continue anyway?', { modal: true }, 'Continue', 'Cancel');
            if (choice !== 'Continue') {
                return;
            }
        }
        const confirm = await vscode.window.showWarningMessage('⚠️  Enabling auto-approve lets Claude execute ANY command (including bash) without asking. Are you sure?', { modal: true }, 'Enable Auto-Approve', 'Cancel');
        if (confirm !== 'Enable Auto-Approve') {
            return;
        }
    }
    // Apply Claude Code settings at the Global scope so they affect all workspaces
    const target = vscode.ConfigurationTarget.Global;
    try {
        await applyClaudeSettings(nextEnabled ? SETTINGS_ON : SETTINGS_OFF, target);
    }
    catch (err) {
        vscode.window.showErrorMessage(`Claude Automator: Failed to update settings – ${String(err)}`);
        return;
    }
    // Persist our own toggle state
    await ourConfig.update('enabled', nextEnabled, vscode.ConfigurationTarget.Global);
    // Refresh the status bar
    updateStatusBar(nextEnabled);
    // Notify the user
    if (nextEnabled) {
        vscode.window.showWarningMessage('⚡ Claude Auto-Approve is now ON. Claude Code will bypass all permission prompts.');
    }
    else {
        vscode.window.showInformationMessage('🛡️ Claude Auto-Approve is now OFF. Normal permission prompts restored.');
    }
}
// ── Extension lifecycle ──────────────────────────────────────────────────────
function activate(context) {
    // Create the status bar button (right-aligned, high priority to keep it visible)
    statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 100);
    statusBarItem.command = 'claudeAutomator.toggleAutoApprove';
    context.subscriptions.push(statusBarItem);
    // Initialise the status bar from the persisted config value
    const enabled = vscode.workspace
        .getConfiguration(EXT_ID)
        .get('enabled', false);
    updateStatusBar(enabled);
    // Register the toggle command
    const disposable = vscode.commands.registerCommand('claudeAutomator.toggleAutoApprove', () => toggleAutoApprove(context));
    context.subscriptions.push(disposable);
    // React to external config changes (e.g. settings.json edits)
    context.subscriptions.push(vscode.workspace.onDidChangeConfiguration((e) => {
        if (e.affectsConfiguration(`${EXT_ID}.enabled`)) {
            const newEnabled = vscode.workspace
                .getConfiguration(EXT_ID)
                .get('enabled', false);
            updateStatusBar(newEnabled);
        }
    }));
}
function deactivate() {
    // VS Code disposes subscriptions automatically; nothing extra needed.
}
//# sourceMappingURL=extension.js.map