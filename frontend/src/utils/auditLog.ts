export interface UiAuditEntry {
  ts: string;
  action: string;
  ok: boolean;
  details?: string;
}

const listeners: Array<(entries: UiAuditEntry[]) => void> = [];
let entries: UiAuditEntry[] = [];

export function addAuditEntry(entry: UiAuditEntry): void {
  entries = [entry, ...entries].slice(0, 50);
  listeners.forEach((l) => l(entries));
}

export function subscribeAudit(callback: (entries: UiAuditEntry[]) => void): () => void {
  listeners.push(callback);
  callback(entries);
  return () => {
    const idx = listeners.indexOf(callback);
    if (idx >= 0) listeners.splice(idx, 1);
  };
}

export function getAuditEntries(): UiAuditEntry[] {
  return entries;
}
