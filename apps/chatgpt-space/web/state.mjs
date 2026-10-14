import { snapshotSchema } from '../shared/contract.mjs';

export function createDeskState({ callTool, render, busy, report, clear }) {
  let generation = 0;
  let latest = null;
  let lastRequest = null;
  function read(result) {
    if (result?.isError) throw new Error('Tool failed');
    return snapshotSchema.parse(result?.structuredContent);
  }
  return {
    receive(result) {
      generation += 1;
      busy(false);
      try {
        latest = read(result);
        clear();
        render(latest, false);
      } catch { report('The host returned an unsupported result. The previous view has been kept.'); }
    },
    async run(name, args) {
      const request = ++generation;
      lastRequest = { name, args: structuredClone(args) };
      clear();
      busy(true);
      try {
        const result = read(await callTool(name, args));
        // A newer host result or selection always wins over a delayed response.
        if (request !== generation) return;
        latest = result;
        render(latest, true);
      } catch {
        if (request === generation) report('The demo could not be loaded. Nothing was changed or shared.', true);
      } finally { if (request === generation) busy(false); }
    },
    retry() { if (lastRequest) return this.run(lastRequest.name, lastRequest.args); },
    cancel() {
      generation += 1;
      busy(false);
      report('The request was cancelled. Nothing was changed or shared.');
    },
    get snapshot() { return latest; },
  };
}
