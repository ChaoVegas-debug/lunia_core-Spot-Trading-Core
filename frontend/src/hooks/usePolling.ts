import { useEffect, useRef } from 'react';

export function usePolling(task: (signal: AbortSignal) => void | Promise<void>, intervalMs: number, deps: unknown[] = []): void {
  const inFlightRef = useRef(false);
  const timerRef = useRef<number | null>(null);
  const controllerRef = useRef<AbortController | null>(null);
  const mountedRef = useRef(true);

  useEffect(() => {
    mountedRef.current = true;

    const run = async () => {
      // SKIP-IF-BUSY: Only one task in-flight at a time
      if (inFlightRef.current) {
        return;
      }

      inFlightRef.current = true;
      controllerRef.current = new AbortController();

      try {
        await task(controllerRef.current.signal);
      } catch (err) {
        if (!mountedRef.current) return;

        // SILENT ABORT: Don't log as error
        if ((err as Error)?.name === 'AbortError' || controllerRef.current?.signal.aborted) {
          return;
        }

        console.error('Polling task failed', err);
      } finally {
        inFlightRef.current = false;
        controllerRef.current = null;
      }
    };

    // Initial run
    run();

    // SINGLE INTERVAL GUARD: Clear existing before creating new
    if (timerRef.current !== null) {
      window.clearInterval(timerRef.current);
    }

    timerRef.current = window.setInterval(() => {
      run();
    }, intervalMs);

    return () => {
      mountedRef.current = false;

      // Cleanup: abort current task
      if (controllerRef.current) {
        controllerRef.current.abort();
      }

      // Clear interval
      if (timerRef.current !== null) {
        window.clearInterval(timerRef.current);
        timerRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);
}
