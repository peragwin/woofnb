import * as vscode from 'vscode';
import { spawn } from 'child_process';
import * as fs from 'fs';

function getConfig() {
  const cfg = vscode.workspace.getConfiguration('woofnb');
  const runner = cfg.get<string>('runnerCommand', 'woof');
  const extra = cfg.get<string[]>('runnerArgs', []);
  const includeDeps = cfg.get<boolean>('runCellIncludesDeps', true);
  return { runner, extra, includeDeps };
}

function sidecarPath(uri: vscode.Uri): vscode.Uri {
  return uri.with({ path: uri.path + '.out' });
}

type SidecarEntry = { cell: string; outputs: any[] };

async function readSidecar(uri: vscode.Uri): Promise<Map<string, any[]>> {
  const p = sidecarPath(uri);
  try {
    const bytes = await vscode.workspace.fs.readFile(p);
    const text = new TextDecoder().decode(bytes);
    const map = new Map<string, any[]>();
    for (const line of text.split(/\r?\n/)) {
      const s = line.trim();
      if (!s) continue;
      try {
        const obj = JSON.parse(s) as SidecarEntry;
        map.set(obj.cell, obj.outputs || []);
      } catch { /* ignore */ }
    }
    return map;
  } catch {
    return new Map();
  }
}

function toCellOutputs(outputs: any[]): vscode.NotebookCellOutput[] {
  const items: vscode.NotebookCellOutputItem[] = [];
  for (const o of outputs) {
    const t = o.output_type;
    if (t === 'stream') {
      const name = o.name || 'stdout';
      const text = String(o.text ?? '');
      const mime = name === 'stderr' ? 'text/x.stderr' : 'text/plain';
      items.push(vscode.NotebookCellOutputItem.text(text, mime));
    } else if (t === 'execute_result' || t === 'display_data') {
      // Prefer text/plain if present
      const data = o.data || {};
      if (data['text/plain']) {
        items.push(vscode.NotebookCellOutputItem.text(String(data['text/plain']), 'text/plain'));
      } else if (o.repr) {
        items.push(vscode.NotebookCellOutputItem.text(String(o.repr), 'text/plain'));
      }
    } else if (t === 'error') {
      const en = o.ename || 'Error';
      const ev = o.evalue || '';
      const tb = Array.isArray(o.traceback) ? o.traceback.join('\n') : '';
      const msg = [en, ev, tb].filter(Boolean).join('\n');
      items.push(vscode.NotebookCellOutputItem.text(msg || 'Error', 'text/x.stderr'));
    } else if (o.repr) {
      items.push(vscode.NotebookCellOutputItem.text(String(o.repr), 'text/plain'));
    }
  }
  return items.length ? [new vscode.NotebookCellOutput(items)] : [];
}

export class WoofNotebookController implements vscode.Disposable {
  private controller: vscode.NotebookController;
  private output: vscode.OutputChannel;

  constructor() {
    this.controller = vscode.notebooks.createNotebookController(
      'woofnb-exec',
      'woofnb',
      'WOOF Notebook'
    );
    this.controller.supportsExecutionOrder = true;
    this.controller.executeHandler = async (cells, _doc, _ct) => {
      if (!cells.length) return;
      await this.runCells(cells);
    };

    this.output = vscode.window.createOutputChannel('WOOF');
  }

  dispose() {
    this.controller.dispose();
    this.output.dispose();
  }

  async runAll(doc: vscode.NotebookDocument) {
    const { runner, extra } = getConfig();
    await this.runCommand([runner, ...extra, 'run', doc.uri.fsPath], doc);
    await this.refreshOutputs(doc);
  }

  async runTests(doc: vscode.NotebookDocument) {
    const { runner, extra } = getConfig();
    await this.runCommand([runner, ...extra, 'test', doc.uri.fsPath], doc);
    await this.refreshOutputs(doc);
  }

  async runCells(cells: readonly vscode.NotebookCell[], includeDeps?: boolean) {
    if (!cells.length) return;
    const doc = cells[0]!.notebook;
    const { runner, extra, includeDeps: cfgDeps } = getConfig();
    const useDeps = includeDeps ?? cfgDeps;

    // Start execution visuals
    const execs = new Map<string, vscode.NotebookCellExecution>();
    for (const c of cells) {
      const id = (c.metadata as any)?.id as string | undefined;
      const ex = this.controller.createNotebookCellExecution(c);
      ex.start(Date.now());
      ex.clearOutput();
      execs.set(id || c.index.toString(), ex);
    }

    const args = [runner, ...extra, 'run', doc.uri.fsPath];
    const ids = new Set<string>();
    for (const c of cells) {
      const id = (c.metadata as any)?.id as string | undefined;
      if (id) { args.push('--cell', id); ids.add(id); }
    }
    if (!useDeps) args.push('--no-deps');

    await this.runCommand(args, doc);
    const map = await readSidecar(doc.uri);

    // Update outputs of selected cells and any deps that ran
    const ranIds = new Set<string>([...map.keys()]);
    for (const c of doc.getCells()) {
      const cid = (c.metadata as any)?.id as string | undefined;
      if (!cid || !ranIds.has(cid)) continue;
      const out = toCellOutputs(map.get(cid) || []);
      // If we created an exec for this cell, use it; else create transient to show updated outputs
      let ex = execs.get(cid);
      if (!ex) {
        ex = this.controller.createNotebookCellExecution(c);
        ex.start(Date.now());
        ex.clearOutput();
      }
      await ex.replaceOutput(out);
      ex.end(true, Date.now());
    }

    // End any execs that didn't get outputs
    for (const ex of execs.values()) {
      if (!ex.didEnd) ex.end(true, Date.now());
    }
  }

  async lint(doc: vscode.NotebookDocument) {
    const { runner, extra } = getConfig();
    await this.runCommand([runner, ...extra, 'lint', doc.uri.fsPath], doc);
  }

  async format(doc: vscode.NotebookDocument) {
    const { runner, extra } = getConfig();
    await this.runCommand([runner, ...extra, 'fmt', doc.uri.fsPath], doc);
    try {
      await vscode.workspace.fs.stat(doc.uri); // touch to ensure file exists
      await vscode.workspace.fs.readFile(doc.uri); // prompt file watcher
      await vscode.commands.executeCommand('workbench.action.files.revert');
    } catch { /* ignore */ }
  }

  async clean(doc: vscode.NotebookDocument) {
    const { runner, extra } = getConfig();
    await this.runCommand([runner, ...extra, 'clean', doc.uri.fsPath], doc);
  }

  private async refreshOutputs(doc: vscode.NotebookDocument) {
    const map = await readSidecar(doc.uri);
    for (const c of doc.getCells()) {
      const cid = (c.metadata as any)?.id as string | undefined;
      if (!cid) continue;
      const outputs = map.get(cid);
      if (!outputs) continue;
      const ex = this.controller.createNotebookCellExecution(c);
      ex.start(Date.now());
      ex.clearOutput();
      await ex.replaceOutput(toCellOutputs(outputs));
      ex.end(true, Date.now());
    }
  }

  private runCommand(cmd: string[], doc?: vscode.NotebookDocument): Promise<void> {
    return new Promise((resolve) => {
      const [exe, ...args] = cmd;
      const proc = spawn(exe, args, { cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath, shell: process.platform === 'win32' });
      this.output.appendLine(`$ ${cmd.join(' ')}`);
      proc.stdout.on('data', (d) => this.output.append(d.toString()));
      proc.stderr.on('data', (d) => this.output.append(d.toString()));
      proc.on('close', (_code) => {
        if (doc) {
          // Try to refresh sidecar from disk immediately
          // No-op: actual reading happens in callers
        }
        resolve();
      });
    });
  }
}

