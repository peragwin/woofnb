import * as vscode from 'vscode';

// Minimal parser/serializer for WOOFNB: header + fenced ```cell blocks
// We preserve the full header text in notebook.metadata.header_text and each
// cell's header token string in cell.metadata.header_tokens_raw (and parsed id/type).

function parseCellHeaderTokens(s: string): Record<string, string> {
  const out: Record<string, string> = {};
  let i = 0;
  const n = s.length;
  function skipWs() { while (i < n && /\s/.test(s[i]!)) i++; }
  function readKey(): string {
    const start = i; while (i < n && s[i] !== '=' && !/\s/.test(s[i]!)) i++; return s.slice(start, i);
  }
  function readValue(): string {
    if (s[i] === '"') {
      i++; let val = '';
      while (i < n) { const ch = s[i] as string; if (ch === '\\') { i++; if (i < n) { val += s[i]; i++; } } else if (ch === '"') { i++; break; } else { val += ch; i++; } }
      return val;
    }
    const start = i; while (i < n && !/\s/.test(s[i]!)) i++; return s.slice(start, i);
  }
  while (i < n) {
    skipWs(); if (i >= n) break; const key = readKey(); skipWs(); if (s[i] === '=') { i++; skipWs(); const val = readValue(); out[key] = val; } else { // bare flag?
      out[key] = 'true';
    }
  }
  return out;
}

export class WoofNotebookSerializer implements vscode.NotebookSerializer {
  async deserializeNotebook(content: Uint8Array, _token: vscode.CancellationToken): Promise<vscode.NotebookData> {
    const text = new TextDecoder().decode(content);
    const lines = text.split(/\r?\n/);

    // Find magic header line and first cell fence
    let idx = 0;
    while (idx < lines.length && !lines[idx]!.trim().startsWith('%WOOFNB')) idx++;
    if (idx >= lines.length) {
      throw new Error("Missing %WOOFNB magic header line");
    }
    const headerParts: string[] = [lines[idx]!];
    idx++;
    while (idx < lines.length && !lines[idx]!.trimStart().startsWith('```cell')) {
      headerParts.push(lines[idx]!);
      idx++;
    }
    const headerText = (headerParts.join('\n') + '\n');

    const cells: vscode.NotebookCellData[] = [];
    while (idx < lines.length) {
      const line = lines[idx]!;
      if (!line.trimStart().startsWith('```cell')) { idx++; continue; }
      const after = line.trimStart().slice('```cell'.length).trim();
      const tokens = parseCellHeaderTokens(after);
      const id = tokens['id'] || '';
      const type = tokens['type'] || 'code';
      // body
      idx++;
      const body: string[] = [];
      while (idx < lines.length && lines[idx]!.trim() !== '```') { body.push(lines[idx]!); idx++; }
      if (idx < lines.length && lines[idx]!.trim() === '```') idx++;

      const kind = vscode.NotebookCellKind.Code; // keep all as code for now
      const cell = new vscode.NotebookCellData(kind, body.join('\n'), 'python');
      cell.metadata = {
        id,
        type,
        header_tokens_raw: after,
      };
      cells.push(cell);
    }

    const nb = new vscode.NotebookData(cells);
    nb.metadata = { header_text: headerText };
    return nb;
  }

  async serializeNotebook(data: vscode.NotebookData, _token: vscode.CancellationToken): Promise<Uint8Array> {
    const header: string = (data.metadata as any)?.header_text || '%WOOFNB 1.0\nname: notebook\n';
    const parts: string[] = [header.trimEnd() + '\n'];
    for (const c of data.cells) {
      const md = (c.metadata || {}) as any;
      const headerTokens = md.header_tokens_raw as string | undefined;
      const id = (md.id as string) || '';
      const type = (md.type as string) || 'code';
      const tokens = headerTokens || `id=${id || 'cell'} type=${type}`;
      parts.push('```cell ' + tokens + '\n');
      parts.push(c.value);
      if (!c.value.endsWith('\n')) parts.push('\n');
      parts.push('```\n');
    }
    const out = parts.join('');
    return new TextEncoder().encode(out.endsWith('\n') ? out : out + '\n');
  }
}
