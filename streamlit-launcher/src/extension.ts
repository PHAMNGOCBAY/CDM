import * as vscode from 'vscode';
import * as cp from 'child_process';
import * as path from 'path';

// ── Types ─────────────────────────────────────────────────────────────────────

type AppState = 'stopped' | 'starting' | 'running' | 'error';

// ── Globals ───────────────────────────────────────────────────────────────────

let streamlitProcess: cp.ChildProcess | undefined;
let state: AppState = 'stopped';
let outputChannel: vscode.OutputChannel;
let statusBarRun: vscode.StatusBarItem;
let statusBarRestart: vscode.StatusBarItem;
let statusBarOpen: vscode.StatusBarItem;

// ── Config helper ─────────────────────────────────────────────────────────────

function cfg<T>(key: string): T {
  return vscode.workspace.getConfiguration('streamlitLauncher').get<T>(key) as T;
}

function getWorkspaceRoot(): string {
  const folders = vscode.workspace.workspaceFolders;
  return folders ? folders[0].uri.fsPath : (process as NodeJS.Process).cwd();
}

// ── Status bar ────────────────────────────────────────────────────────────────

function updateStatusBar(): void {
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
      statusBarRun.tooltip = 'Streamlit đang khởi động, vui lòng chờ';
      statusBarRun.backgroundColor = new vscode.ThemeColor('statusBarItem.warningBackground');
      statusBarRestart.hide();
      statusBarOpen.hide();
      break;

    case 'running':
      const port = cfg<number>('port');
      statusBarRun.text = `$(debug-stop) Streamlit: :${port}`;
      statusBarRun.tooltip = `Streamlit đang chạy trên port ${port} — Click để DỪNG`;
      statusBarRun.backgroundColor = new vscode.ThemeColor('statusBarItem.errorBackground');
      statusBarRun.color = undefined;
      statusBarRestart.show();
      statusBarOpen.show();
      break;

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

// ── Start / Stop ──────────────────────────────────────────────────────────────

function startApp(): void {
  if (state === 'running' || state === 'starting') {
    return;
  }

  const workspaceRoot = getWorkspaceRoot();
  const pythonPath = cfg<string>('pythonPath') || 'python';
  const scriptPath = cfg<string>('scriptPath') || 'scripts/app_cdm.py';
  const port = cfg<number>('port') || 8503;
  const dbPath = cfg<string>('dbPath');
  const extraArgs = cfg<string>('extraArgs') || '';
  const autoOpen = cfg<boolean>('autoOpenBrowser');

  const absoluteScript = path.isAbsolute(scriptPath)
    ? scriptPath
    : path.join(workspaceRoot, scriptPath);

  const args = [
    '-m', 'streamlit', 'run',
    `"${absoluteScript}"`,
    `--server.port`, String(port),
    '--server.headless', 'false',
    ...extraArgs.split(' ').filter(a => a.trim().length > 0),
  ];

  const env: NodeJS.ProcessEnv = { ...(process as NodeJS.Process).env };
  if (dbPath && dbPath.trim()) {
    env['TTHC_DB_PATH'] = dbPath.trim();
    outputChannel.appendLine(`[INFO] TTHC_DB_PATH = ${dbPath.trim()}`);
  }

  outputChannel.clear();
  outputChannel.appendLine(`[INFO] Khởi động Streamlit...`);
  outputChannel.appendLine(`[CMD] ${pythonPath} ${args.join(' ')}`);
  outputChannel.appendLine(`[CWD] ${workspaceRoot}`);
  outputChannel.appendLine('─'.repeat(60));
  outputChannel.show(true);

  setState('starting');

  streamlitProcess = cp.spawn(pythonPath, args, {
    cwd: workspaceRoot,
    env,
    shell: true,
  });

  // Detect "You can now view your Streamlit app" → app is truly running
  const onData = (data: Buffer | string) => {
    const text = data.toString();
    outputChannel.append(text);
    if (state === 'starting' && text.includes('You can now view')) {
      setState('running');
      if (autoOpen) {
        vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${port}`));
      }
      vscode.window.showInformationMessage(
        `🚀 Streamlit đang chạy tại http://localhost:${port}`,
        'Mở trình duyệt'
      ).then(choice => {
        if (choice === 'Mở trình duyệt') {
          vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${port}`));
        }
      });
    }
  };

  streamlitProcess.stdout?.on('data', onData);
  streamlitProcess.stderr?.on('data', onData);

  streamlitProcess.on('exit', (code: number | null) => {
    outputChannel.appendLine(`\n[INFO] Streamlit process kết thúc (exit code: ${code})`);
    if (state === 'running' || state === 'starting') {
      setState(code === 0 || code === null ? 'stopped' : 'error');
      if (code !== 0 && code !== null) {
        vscode.window.showErrorMessage(
          `Streamlit dừng với lỗi (exit ${code}). Xem Output panel để biết chi tiết.`,
          'Xem Log'
        ).then(c => { if (c === 'Xem Log') outputChannel.show(); });
      }
    }
    streamlitProcess = undefined;
  });

  streamlitProcess.on('error', (err: Error) => {
    outputChannel.appendLine(`[ERROR] Không thể khởi động: ${err.message}`);
    outputChannel.appendLine(`[HINT] Kiểm tra Python path trong Settings: streamlitLauncher.pythonPath`);
    setState('error');
    vscode.window.showErrorMessage(`Không thể chạy Streamlit: ${err.message}`);
    streamlitProcess = undefined;
  });
}

function stopApp(): void {
  if (!streamlitProcess) {
    setState('stopped');
    return;
  }
  outputChannel.appendLine('\n[INFO] Đang dừng Streamlit...');
  // Kill process tree on Windows
  if ((process as NodeJS.Process).platform === 'win32' && streamlitProcess.pid) {
    cp.exec(`taskkill /PID ${streamlitProcess.pid} /T /F`, (err: Error | null) => {
      if (err) {
        outputChannel.appendLine(`[WARN] taskkill: ${err.message}`);
      }
    });
  } else {
    streamlitProcess.kill('SIGTERM');
  }
  setState('stopped');
  vscode.window.showInformationMessage('🛑 Streamlit đã dừng.');
}

function restartApp(): void {
  outputChannel.appendLine('\n[INFO] Đang restart Streamlit...');
  stopApp();
  global.setTimeout(() => startApp(), 1500);
}

function setState(s: AppState): void {
  state = s;
  updateStatusBar();
}

// ── Commands ──────────────────────────────────────────────────────────────────

async function configureCommand(): Promise<void> {
  const items: vscode.QuickPickItem[] = [
    { label: '$(gear) Python Path', description: cfg<string>('pythonPath') },
    { label: '$(file-code) Script Path', description: cfg<string>('scriptPath') },
    { label: '$(ports-open-browser-icon) Port', description: String(cfg<number>('port')) },
    { label: '$(database) DB Path (TTHC_DB_PATH)', description: cfg<string>('dbPath') || '(default)' },
    { label: '$(symbol-string) Extra Args', description: cfg<string>('extraArgs') },
  ];

  const choice = await vscode.window.showQuickPick(items, {
    placeHolder: 'Chọn cài đặt để thay đổi',
    title: 'Streamlit Launcher — Cấu hình',
  });

  if (!choice) return;

  if (choice.label.includes('Python Path')) {
    const val = await vscode.window.showInputBox({
      prompt: 'Đường dẫn Python executable',
      value: cfg<string>('pythonPath'),
      placeHolder: 'ví dụ: C:\\Python312\\python.exe',
    });
    if (val !== undefined) {
      await vscode.workspace.getConfiguration('streamlitLauncher').update('pythonPath', val, vscode.ConfigurationTarget.Global);
    }
  } else if (choice.label.includes('Script Path')) {
    const val = await vscode.window.showInputBox({
      prompt: 'File Python (tương đối với workspace root)',
      value: cfg<string>('scriptPath'),
      placeHolder: 'scripts/app_cdm.py',
    });
    if (val !== undefined) {
      await vscode.workspace.getConfiguration('streamlitLauncher').update('scriptPath', val, vscode.ConfigurationTarget.Global);
    }
  } else if (choice.label.includes('Port')) {
    const val = await vscode.window.showInputBox({
      prompt: 'Cổng server Streamlit',
      value: String(cfg<number>('port')),
      placeHolder: '8503',
      validateInput: v => isNaN(parseInt(v)) ? 'Nhập số nguyên' : undefined,
    });
    if (val !== undefined) {
      await vscode.workspace.getConfiguration('streamlitLauncher').update('port', parseInt(val), vscode.ConfigurationTarget.Global);
    }
  } else if (choice.label.includes('DB Path')) {
    const val = await vscode.window.showInputBox({
      prompt: 'Đường dẫn TTHC.sqlite (để trống = dùng default trong code)',
      value: cfg<string>('dbPath'),
      placeHolder: 'C:\\Users\\bayng\\TTHC_local\\TTHC.sqlite',
    });
    if (val !== undefined) {
      await vscode.workspace.getConfiguration('streamlitLauncher').update('dbPath', val, vscode.ConfigurationTarget.Global);
    }
  } else if (choice.label.includes('Extra Args')) {
    const val = await vscode.window.showInputBox({
      prompt: 'Tham số thêm cho lệnh streamlit run',
      value: cfg<string>('extraArgs'),
      placeHolder: '--server.runOnSave true',
    });
    if (val !== undefined) {
      await vscode.workspace.getConfiguration('streamlitLauncher').update('extraArgs', val, vscode.ConfigurationTarget.Global);
    }
  }

  vscode.window.showInformationMessage('✅ Đã lưu cài đặt Streamlit Launcher.');
}

// ── Activation ────────────────────────────────────────────────────────────────

export function activate(context: vscode.ExtensionContext): void {
  // Output channel
  outputChannel = vscode.window.createOutputChannel('Streamlit');
  context.subscriptions.push(outputChannel);

  // Status bar — main toggle (rightmost)
  statusBarRun = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 200);
  statusBarRun.command = 'streamlitLauncher.toggle';
  context.subscriptions.push(statusBarRun);

  // Status bar — restart button
  statusBarRestart = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 199);
  statusBarRestart.text = '$(refresh)';
  statusBarRestart.tooltip = 'Restart Streamlit';
  statusBarRestart.command = 'streamlitLauncher.restart';
  context.subscriptions.push(statusBarRestart);

  // Status bar — open browser button
  statusBarOpen = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Right, 198);
  statusBarOpen.text = '$(globe)';
  statusBarOpen.tooltip = `Mở http://localhost:${cfg<number>('port')} trong trình duyệt`;
  statusBarOpen.command = 'streamlitLauncher.openBrowser';
  context.subscriptions.push(statusBarOpen);

  updateStatusBar();

  // Register commands
  context.subscriptions.push(
    vscode.commands.registerCommand('streamlitLauncher.toggle', () => {
      state === 'running' || state === 'starting' ? stopApp() : startApp();
    }),
    vscode.commands.registerCommand('streamlitLauncher.restart', restartApp),
    vscode.commands.registerCommand('streamlitLauncher.openBrowser', () => {
      vscode.env.openExternal(vscode.Uri.parse(`http://localhost:${cfg<number>('port')}`));
    }),
    vscode.commands.registerCommand('streamlitLauncher.configure', configureCommand),
  );

  // Auto-configure defaults từ project của bạn nếu chưa có
  autoDetectConfig();
}

function autoDetectConfig(): void {
  const config = vscode.workspace.getConfiguration('streamlitLauncher');
  // Set default Python path nếu chưa cấu hình
  if (config.get('pythonPath') === 'python') {
    config.update(
      'pythonPath',
      'C:\\Users\\bayng\\AppData\\Local\\Programs\\Python\\Python312\\python.exe',
      vscode.ConfigurationTarget.Global
    );
  }
  // Set default DB path
  if (!config.get('dbPath')) {
    config.update(
      'dbPath',
      'C:\\Users\\bayng\\TTHC_local\\TTHC.sqlite',
      vscode.ConfigurationTarget.Global
    );
  }
}

export function deactivate(): void {
  if (streamlitProcess) {
    stopApp();
  }
}
