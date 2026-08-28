'use strict';

const vscode = require('vscode');
const cp = require('child_process');
const path = require('path');

// ── State ─────────────────────────────────────────────────────────────────────

let streamlitProcess = undefined;
let state = 'stopped'; // 'stopped' | 'starting' | 'running' | 'error'
let outputChannel;
let statusBarRun;
let statusBarRestart;
let statusBarOpen;

// ── Config ────────────────────────────────────────────────────────────────────

function cfg(key) {
  return vscode.workspace.getConfiguration('streamlitLauncher').get(key);
}

function getWorkspaceRoot() {
  const folders = vscode.workspace.workspaceFolders;
  return folders ? folders[0].uri.fsPath : process.cwd();
}

// ── Status bar ────────────────────────────────────────────────────────────────

function updateStatusBar() {
  switch (state) {
    case 'stopped':
      statusBarRun.text = '$(play) Streamlit: OFF';
      statusBarRun.tooltip = 'Click để khởi động Streamlit app';
      statusBarRun.backgroundColor = undefined;
      statusBarRun.color = undefined;
      statusBarRestart.hide();
      statusBarOpen.hide();
      break;
    case 'starting':
      statusBarRun.text = '$(loading~spin) Streamlit: Đang khởi động…';
      statusBarRun.tooltip = 'Streamlit đang khởi động...';
      statusBarRun.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
      statusBarRestart.hide();
      statusBarOpen.hide();
      break;
    case 'running': {
      const port = cfg('port');
      statusBarRun.text = `$(debug-stop) Streamlit: :${port}`;
      statusBarRun.tooltip = `Streamlit đang chạy port ${port} — Click để DỪNG`;
      statusBarRun.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
      statusBarRun.color = undefined;
      statusBarRestart.show();
      statusBarOpen.show();
      break;
    }
    case 'error':
      statusBarRun.text = '$(error) Streamlit: Lỗi';
      statusBarRun.tooltip = 'Streamlit gặp lỗi — Click để thử lại';
      statusBarRun.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
      statusBarRestart.hide();
      statusBarOpen.hide();
      break;
  }
  statusBarRun.show();
}

function setState(s) {
  state = s;
  updateStatusBar();
}

// ── Start ─────────────────────────────────────────────────────────────────────

function startApp() {
  if (state === 'running' || state === 'starting') { return; }

  const workspaceRoot = getWorkspaceRoot();
  const pythonPath = cfg('pythonPath') || 'python';
  const scriptPath = cfg('scriptPath') || 'scripts/app_cdm.py';
  const port = cfg('port') || 8503;
  const dbPath = cfg('dbPath') || '';
  const extraArgs = (cfg('extraArgs') || '').split(' ').filter(a => a.trim());
  const autoOpen = cfg('autoOpenBrowser') !== false;

  const absoluteScript = path.isAbsolute(scriptPath)
    ? scriptPath
    : path.join(workspaceRoot, scriptPath);

  const args = [
    '-m', 'streamlit', 'run', `"${absoluteScript}"`,
    '--server.port', String(port),
    '--server.headless', 'false',
    ...extraArgs,
  ];

  const env = Object.assign({}, process.env);
  if (dbPath.trim()) {
    env['TTHC_DB_PATH'] = dbPath.trim();
    outputChannel.appendLine(`[INFO] TTHC_DB_PATH = ${dbPath.trim()}`);
  }

  outputChannel.clear();
  outputChannel.appendLine('[INFO] Khởi động Streamlit...');
  outputChannel.appendLine(`[CMD] ${pythonPath} ${args.join(' ')}`);
  outputChannel.appendLine(`[CWD] ${workspaceRoot}`);
  outputChannel.appendLine('─'.repeat(60));
  outputChannel.show(true);

  setState('starting');

  streamlitProcess = cp.spawn(pythonPath, args, { cwd: workspaceRoot, env, shell: true });

  const onData = (data) => {
    const text = String(data);
    outputChannel.append(text);
    if (state === 'starting' && text.includes('You can now view')) {
      setState('running');
      if (autoOpen) {
        vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${port}`));
      }
      vscode.window.showInformationMessage(
        `🚀 Streamlit đang chạy tại http://localhost:${port}`,
        'Mở trình duyệt'
      ).then(c => {
        if (c === 'Mở trình duyệt') {
          vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${port}`));
        }
      });
    }
  };

  streamlitProcess.stdout && streamlitProcess.stdout.on('data', onData);
  streamlitProcess.stderr && streamlitProcess.stderr.on('data', onData);

  streamlitProcess.on('exit', (code) => {
    outputChannel.appendLine(`\n[INFO] Streamlit kết thúc (exit code: ${code})`);
    if (state === 'running' || state === 'starting') {
      setState(code === 0 || code === null ? 'stopped' : 'error');
      if (code !== 0 && code !== null) {
        vscode.window.showErrorMessage(
          `Streamlit dừng với lỗi (exit ${code}).`,
          'Xem Log'
        ).then(c => { if (c === 'Xem Log') { outputChannel.show(); } });
      }
    }
    streamlitProcess = undefined;
  });

  streamlitProcess.on('error', (err) => {
    outputChannel.appendLine(`[ERROR] Không thể khởi động: ${err.message}`);
    outputChannel.appendLine('[HINT] Kiểm tra streamlitLauncher.pythonPath trong Settings');
    setState('error');
    vscode.window.showErrorMessage(`Không thể chạy Streamlit: ${err.message}`);
    streamlitProcess = undefined;
  });
}

// ── Stop ──────────────────────────────────────────────────────────────────────

function stopApp() {
  if (!streamlitProcess) { setState('stopped'); return; }
  outputChannel.appendLine('\n[INFO] Đang dừng Streamlit...');
  const pid = streamlitProcess.pid;
  if (process.platform === 'win32' && pid) {
    cp.exec(`taskkill /PID ${pid} /T /F`, (err) => {
      if (err) { outputChannel.appendLine(`[WARN] taskkill: ${err.message}`); }
    });
  } else {
    streamlitProcess.kill('SIGTERM');
  }
  streamlitProcess = undefined;
  setState('stopped');
  vscode.window.showInformationMessage('🛑 Streamlit đã dừng.');
}

function restartApp() {
  outputChannel.appendLine('\n[INFO] Đang restart Streamlit...');
  stopApp();
  setTimeout(() => startApp(), 1500);
}

// ── Configure ─────────────────────────────────────────────────────────────────

async function configureCommand() {
  const items = [
    { label: '$(gear) Python Path', description: cfg('pythonPath') },
    { label: '$(file-code) Script Path', description: cfg('scriptPath') },
    { label: '$(ports-open-browser-icon) Port', description: String(cfg('port')) },
    { label: '$(database) DB Path (TTHC_DB_PATH)', description: cfg('dbPath') || '(default)' },
    { label: '$(symbol-string) Extra Args', description: cfg('extraArgs') },
  ];

  const choice = await vscode.window.showQuickPick(items, {
    placeHolder: 'Chọn cài đặt để thay đổi',
    title: 'Streamlit Launcher — Cấu hình',
  });
  if (!choice) { return; }

  const scoped = vscode.workspace.getConfiguration('streamlitLauncher');
  const G = vscode.ConfigurationTarget.Global;

  if (choice.label.includes('Python Path')) {
    const v = await vscode.window.showInputBox({ prompt: 'Python executable path', value: cfg('pythonPath') });
    if (v !== undefined) { await scoped.update('pythonPath', v, G); }
  } else if (choice.label.includes('Script Path')) {
    const v = await vscode.window.showInputBox({ prompt: 'Script (tương đối với workspace root)', value: cfg('scriptPath') });
    if (v !== undefined) { await scoped.update('scriptPath', v, G); }
  } else if (choice.label.includes('Port')) {
    const v = await vscode.window.showInputBox({
      prompt: 'Port', value: String(cfg('port')),
      validateInput: x => isNaN(parseInt(x)) ? 'Nhập số nguyên' : undefined,
    });
    if (v !== undefined) { await scoped.update('port', parseInt(v), G); }
  } else if (choice.label.includes('DB Path')) {
    const v = await vscode.window.showInputBox({ prompt: 'TTHC_DB_PATH (để trống = default)', value: cfg('dbPath') });
    if (v !== undefined) { await scoped.update('dbPath', v, G); }
  } else if (choice.label.includes('Extra Args')) {
    const v = await vscode.window.showInputBox({ prompt: 'Extra args', value: cfg('extraArgs') });
    if (v !== undefined) { await scoped.update('extraArgs', v, G); }
  }
  vscode.window.showInformationMessage('✅ Đã lưu cài đặt.');
}

// ── Lifecycle ─────────────────────────────────────────────────────────────────

function activate(context) {
  outputChannel = vscode.window.createOutputChannel('Streamlit');
  context.subscriptions.push(outputChannel);

  statusBarRun = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 200);
  statusBarRun.command = 'streamlitLauncher.toggle';
  context.subscriptions.push(statusBarRun);

  statusBarRestart = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 199);
  statusBarRestart.text = '$(refresh)';
  statusBarRestart.tooltip = 'Restart Streamlit';
  statusBarRestart.command = 'streamlitLauncher.restart';
  context.subscriptions.push(statusBarRestart);

  statusBarOpen = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 198);
  statusBarOpen.text = '$(globe)';
  statusBarOpen.tooltip = 'Mở trình duyệt';
  statusBarOpen.command = 'streamlitLauncher.openBrowser';
  context.subscriptions.push(statusBarOpen);

  updateStatusBar();

  context.subscriptions.push(
    vscode.commands.registerCommand('streamlitLauncher.toggle', () => {
      (state === 'running' || state === 'starting') ? stopApp() : startApp();
    }),
    vscode.commands.registerCommand('streamlitLauncher.restart', restartApp),
    vscode.commands.registerCommand('streamlitLauncher.openBrowser', () => {
      vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${cfg('port')}`));
    }),
    vscode.commands.registerCommand('streamlitLauncher.configure', configureCommand),
  );

  // Auto-detect defaults cho project TTHC
  const scoped = vscode.workspace.getConfiguration('streamlitLauncher');
  const G = vscode.ConfigurationTarget.Global;
  if (scoped.get('pythonPath') === 'python') {
    scoped.update('pythonPath',
      'C:\\Users\\bayng\\AppData\\Local\\Programs\\Python\\Python312\\python.exe', G);
  }
  if (!scoped.get('dbPath')) {
    scoped.update('dbPath', 'C:\\Users\\bayng\\TTHC_local\\TTHC.sqlite', G);
  }
}

function deactivate() {
  if (streamlitProcess) { stopApp(); }
}

module.exports = { activate, deactivate };