import { useEffect, useRef } from 'react';

export function usePolling(task: (signal: AbortSignal) => void | Promise<void>, intervalMs: number, deps: unknown[] = []): void {
  const controllerRef = useRef<AbortController | null>(null);

  useEffect(() => {
    let stopped = false;
    controllerRef.current = new AbortController();

    const run = async () => {
      try {
        await task(controllerRef.current!.signal);
      } catch (err) {
        if (controllerRef.current?.signal.aborted) {
          return;
        }
        console.error('Polling task failed', err);
      }
    };

    run();
    const id = window.setInterval(() => {
      controllerRef.current?.abort();
      controllerRef.current = new AbortController();
      if (!stopped) {
        run();
      }
    }, intervalMs);

    return () => {
      stopped = true;
      controllerRef.current?.abort();
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
