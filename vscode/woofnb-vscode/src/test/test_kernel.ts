
import * as assert from 'assert';
import * as mock from './mock_vscode';
import { EventEmitter } from 'events';
import { PassThrough } from 'stream';

// Mock VS Code
const Module = require('module');
const originalRequire = Module.prototype.require;

// Mock configuration
const mockConfig: any = {
    'woofnb.runnerCommand': 'woof',
    'woofnb.runnerArgs': [],
    'woofnb.runCellIncludesDeps': true
};

const mockWorkspace = {
    getConfiguration: (section: string) => ({
        get: (key: string, defaultValue: any) => {
            const fullKey = section + '.' + key;
            return mockConfig[fullKey] !== undefined ? mockConfig[fullKey] : defaultValue;
        }
    }),
    fs: {
        readFile: async (uri: any) => {
             // Mock sidecar for refreshOutputs
             return new TextEncoder().encode("");
        },
        stat: async () => ({})
    },
    workspaceFolders: [{ uri: { fsPath: '/tmp/workspace' } }]
};

const mockWindow = {
    createOutputChannel: () => ({
        append: () => {},
        appendLine: () => {},
        dispose: () => {}
    }),
    activeNotebookEditor: undefined as any
};

const mockNotebooks = {
    createNotebookController: () => ({
        createNotebookCellExecution: (cell: any) => ({
            start: () => {},
            clearOutput: () => {},
            replaceOutput: (out: any) => { cell.outputs = out; },
            end: () => {},
            token: {}
        }),
        dispose: () => {}
    })
};

// Mock Child Process
class MockChildProcess extends EventEmitter {
    public stdout = new PassThrough();
    public stderr = new PassThrough();
    public stdin = {
        write: (data: string) => {
            // console.log("MOCK_KERNEL_STDIN:", data.trim());
            try {
                const req = JSON.parse(data);
                if (req.command === 'run_cell') {
                    const resp = {
                        id: req.id,
                        status: 'ok',
                        outputs: [
                            { output_type: 'stream', name: 'stdout', text: `Result: ${req.code}` }
                        ]
                    };
                    // console.log("MOCK_KERNEL_STDOUT:", JSON.stringify(resp));
                    this.stdout.write(JSON.stringify(resp) + '\n');
                }
            } catch (e) {
                console.error("Mock kernel error:", e);
            }
        }
    };
    public kill() {
        this.emit('close', 0);
    }
}

const mockChildProcess = {
    spawn: (cmd: string, args: string[], opts: any) => {
        console.log(`MOCK_SPAWN: ${cmd} ${args.join(' ')}`);
        return new MockChildProcess();
    }
};

// Override require
Module.prototype.require = function(request: string) {
    if (request === 'vscode') {
        return {
            ...mock,
            workspace: mockWorkspace,
            window: mockWindow,
            notebooks: mockNotebooks,
            Uri: {
                file: (p: string) => ({ fsPath: p, path: p, with: (change: any) => ({ path: change.path }) })
            },
            NotebookCellOutput: class {
                constructor(public items: any[]) {}
            },
            NotebookCellOutputItem: class {
                static text(val: string, mime: string) { return { value: val, mime }; }
                static json(val: any, mime: string) { return { value: val, mime }; }
                static error(e: Error) { return { value: e.message, mime: 'application/vnd.code.notebook.error' }; }
                constructor(public data: Uint8Array, public mime: string) {}
            }
        };
    }
    if (request === 'child_process') return mockChildProcess;
    return originalRequire.apply(this, arguments);
};

// Import Controller
async function testKernelIntegration() {
    console.log("Starting Kernel Integration Tests...");
    const { WoofNotebookController } = require('../controller');
    const controller = new WoofNotebookController();

    const cells: any[] = [
        {
            metadata: { id: 'c1' },
            index: 0,
            notebook: null as any,
            outputs: [],
            document: { getText: () => "print(1)" }
        }
    ];
    const doc: any = {
        uri: { fsPath: '/tmp/test.woofnb', path: '/tmp/test.woofnb', with: (c: any) => ({ path: c.path }) },
        getCells: () => cells
    };
    cells.forEach(c => c.notebook = doc);

    // Run Cell
    console.log("Testing runCells([c1]) via Kernel...");

    // This should trigger spawn('woof', ['kernel']) and then write to stdin
    await controller.runCells([cells[0]]);

    assert.strictEqual(cells[0].outputs.length, 1, "Output length mismatch");
    const items = cells[0].outputs[0].items;
    assert.strictEqual(items[0].value.trim(), "Result: print(1)");

    console.log("✅ Kernel execution working");

    controller.dispose();
}

testKernelIntegration().catch(e => {
    console.error(e);
    process.exit(1);
});
