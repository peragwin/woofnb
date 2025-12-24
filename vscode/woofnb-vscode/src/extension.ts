import * as vscode from 'vscode';
import { WoofNotebookSerializer } from './serializer';
import { WoofNotebookController } from './controller';

export function activate(context: vscode.ExtensionContext) {
  // Register serializer for WOOF notebooks
  const serializer = new WoofNotebookSerializer();
  context.subscriptions.push(
    vscode.workspace.registerNotebookSerializer('woofnb', serializer, {
      transientOutputs: false,
      transientDocumentMetadata: {
        editable: false,
        runnable: false,
      },
    })
  );

  // Register execution controller
  const controller = new WoofNotebookController();
  context.subscriptions.push(controller);

  // Commands
  context.subscriptions.push(
    vscode.commands.registerCommand('woofnb.runAll', async () => {
      const doc = vscode.window.activeNotebookEditor?.notebook;
      if (doc) {
        await controller.runAll(doc);
      }
    }),
    vscode.commands.registerCommand('woofnb.runTests', async () => {
      const doc = vscode.window.activeNotebookEditor?.notebook;
      if (doc) {
        await controller.runTests(doc);
      }
    }),
    vscode.commands.registerCommand('woofnb.runCellOnly', async () => {
      const ed = vscode.window.activeNotebookEditor;
      if (ed) {
        const cell = ed.selections[0]?.start ? ed.notebook.cellAt(ed.selections[0].start) : undefined;
        if (cell) {
          await controller.runCells([cell], false);
        }
      }
    }),
    vscode.commands.registerCommand('woofnb.lint', async () => {
      const doc = vscode.window.activeNotebookEditor?.notebook;
      if (doc) {
        await controller.lint(doc);
      }
    }),
    vscode.commands.registerCommand('woofnb.format', async () => {
      const doc = vscode.window.activeNotebookEditor?.notebook;
      if (doc) {
        await controller.format(doc);
      }
    }),
    vscode.commands.registerCommand('woofnb.clean', async () => {
      const doc = vscode.window.activeNotebookEditor?.notebook;
      if (doc) {
        await controller.clean(doc);
      }
    })
  );
}

export function deactivate() {}
