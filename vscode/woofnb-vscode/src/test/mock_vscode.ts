// Minimal mock for vscode API to run serializer tests in node
import * as fs from 'fs';
import * as path from 'path';

export enum NotebookCellKind {
    Markup = 1,
    Code = 2
}

export class NotebookCellData {
    public metadata: { [key: string]: any } = {};
    constructor(
        public kind: NotebookCellKind,
        public value: string,
        public languageId: string
    ) {}
}

export class NotebookData {
    public metadata: { [key: string]: any } = {};
    constructor(public cells: NotebookCellData[]) {}
}

export class NotebookCellOutputItem {
    static text(value: string, mime: string = 'text/plain') {
        return { value, mime };
    }
    static json(value: any, mime: string = 'application/json') {
        return { value, mime };
    }
    static error(err: Error) {
        return { value: err, mime: 'application/vnd.code.notebook.error' };
    }
    constructor(public data: Uint8Array, public mime: string) {}
}

export class NotebookCellOutput {
    constructor(public items: any[]) {}
}

// Mock Token
export const CancellationToken = {
    isCancellationRequested: false,
    onCancellationRequested: () => ({ dispose: () => {} })
};

// Mock TextEncoder/Decoder if not in global (Node 11+ has them, but good to be safe)
if (typeof TextEncoder === 'undefined') {
    const util = require('util');
    (global as any).TextEncoder = util.TextEncoder;
    (global as any).TextDecoder = util.TextDecoder;
}
