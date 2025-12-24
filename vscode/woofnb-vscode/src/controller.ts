import * as vscode from 'vscode';
import { spawn, ChildProcessWithoutNullStreams } from 'child_process';
import * as fs from 'fs';
import * as readline from 'readline';

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
      const data = o.data || {};
      for (const mime of Object.keys(data)) {
        const val = data[mime];
        if (mime.startsWith('text/')) {
           items.push(vscode.NotebookCellOutputItem.text(String(val), mime));
        } else if (mime.startsWith('image/')) {
           try {
             const bytes = Buffer.from(String(val), 'base64');
             items.push(new vscode.NotebookCellOutputItem(bytes, mime));
           } catch (e) {
             items.push(vscode.NotebookCellOutputItem.text(String(val), 'text/plain'));
           }
        } else if (mime === 'application/json') {
           items.push(vscode.NotebookCellOutputItem.json(val, mime));
        } else {
           items.push(vscode.NotebookCellOutputItem.text(String(val), mime));
        }
      }
      if (items.length === 0 && o.repr) {
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

class KernelClient implements vscode.Disposable {
    private proc?: ChildProcessWithoutNullStreams;
    private rl?: readline.Interface;
    private pending = new Map<string, { resolve: (v:any)=>void, reject: (e:any)=>void }>();
    private _output: vscode.OutputChannel;

    constructor(output: vscode.OutputChannel) {
        this._output = output;
    }

    start() {
        if (this.proc) return;
        const { runner, extra } = getConfig();
        // Assume 'kernel' command is available
        const args = [...extra, 'kernel'];
        this._output.appendLine(`Starting kernel: ${runner} ${args.join(' ')}`);

        try {
            this.proc = spawn(runner, args, {
                cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath,
                shell: process.platform === 'win32'
            });

            this.rl = readline.createInterface({ input: this.proc.stdout });
            this.rl.on('line', (line) => {
                if (!line.trim()) return;
                try {
                    const msg = JSON.parse(line);
                    const id = msg.id;
                    if (id && this.pending.has(id)) {
                        const { resolve, reject } = this.pending.get(id)!;
                        this.pending.delete(id);
                        if (msg.status === 'ok') {
                            resolve(msg);
                        } else {
                            reject(new Error(msg.error || 'Unknown kernel error'));
                        }
                    } else {
                        // console.log("Unsolicited kernel msg:", msg);
                    }
                } catch (e) {
                    this._output.appendLine(`Kernel stdout parse error: ${line}`);
                }
            });

            this.proc.stderr.on('data', d => {
                 this._output.append(`Kernel stderr: ${d}`);
            });

            this.proc.on('close', (code) => {
                this._output.appendLine(`Kernel exited with code ${code}`);
                this.dispose();
            });

        } catch (e) {
            this._output.appendLine(`Failed to start kernel: ${e}`);
        }
    }

    async runCell(id: string, code: string): Promise<any> {
        if (!this.proc) this.start();
        if (!this.proc) throw new Error("Kernel not running");

        const reqId = Math.random().toString(36).slice(2);
        return new Promise((resolve, reject) => {
            this.pending.set(reqId, { resolve, reject });
            const req = { command: 'run_cell', id: reqId, code };
            this.proc!.stdin.write(JSON.stringify(req) + '\n');
        });
    }

    dispose() {
        if (this.proc) {
            const p = this.proc;
            this.proc = undefined;
            p.kill();
        }
        if (this.rl) {
            this.rl.close();
            this.rl = undefined;
        }
        for (const { reject } of this.pending.values()) {
            reject(new Error("Kernel killed"));
        }
        this.pending.clear();
    }
}

export class WoofNotebookController implements vscode.Disposable {
  private controller: vscode.NotebookController;
  private output: vscode.OutputChannel;
  private kernel?: KernelClient;

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
    this.kernel?.dispose();
  }

  getKernel(): KernelClient {
      if (!this.kernel) {
          this.kernel = new KernelClient(this.output);
          this.kernel.start();
      }
      return this.kernel;
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

    // For now, we only use Kernel for interactive single-cell runs if NOT including deps (or deps are managed by kernel logic?)
    // Actually, `woof kernel` currently only supports `run_cell`. It doesn't handle graph/deps yet.
    // But since the user wants "Jupyter-like kernel", we usually run one cell at a time in the kernel.
    // If we want to run multiple cells, we just send multiple requests.

    // Simplification: Always use Kernel for execution if it's running code.
    // What about "run all"? runAll uses CLI `run` which is robust for batch.
    // Let's use Kernel for interactive `runCells`.

    const k = this.getKernel();

    for (const c of cells) {
      const ex = this.controller.createNotebookCellExecution(c);
      ex.start(Date.now());
      ex.clearOutput();

      try {
          // Get code
          const code = c.document.getText();
          // We also need to send cell_id? Kernel doesn't track it yet but might log it.
          const id = (c.metadata as any)?.id || '';

          // Send to kernel
          const resp = await k.runCell(id, code);

          if (resp.outputs) {
              await ex.replaceOutput(toCellOutputs(resp.outputs));
          }

          // Check for errors
          const hasError = resp.outputs?.some((o: any) => o.output_type === 'error');
          ex.end(!hasError, Date.now());

      } catch (e) {
          const msg = e instanceof Error ? e.message : String(e);
          ex.replaceOutput(new vscode.NotebookCellOutput([
              vscode.NotebookCellOutputItem.error(new Error(msg))
          ]));
          ex.end(false, Date.now());
      }
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
