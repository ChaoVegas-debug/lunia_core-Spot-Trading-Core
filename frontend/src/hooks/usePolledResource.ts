import { useEffect, useState, useCallback } from 'react';

interface ResourceState<T> {
  data?: T;
  error?: Error;
  loading: boolean;
  lastUpdated?: number;
  refresh: () => void;
}

export function usePolledResource<T>(
  fetcher: (signal: AbortSignal) => Promise<T>,
  intervalMs: number,
  deps: unknown[] = []
): ResourceState<T> {
  const [state, setState] = useState<Omit<ResourceState<T>, 'refresh'>>({ loading: true });
  const [refreshKey, setRefreshKey] = useState(0);

  const refresh = useCallback(() => {
    setRefreshKey(k => k + 1);
  }, []);

  useEffect(() => {
    let active = true;
    let controller = new AbortController();

    const run = async () => {
      // Don't set loading true on poll, only initial or refresh if desired (optional)
      // setState(prev => ({ ...prev, loading: true }));
      try {
        const result = await fetcher(controller.signal);
        if (!active) return;
        setState({ data: result, loading: false, lastUpdated: Date.now() });
      } catch (err) {
        if (!active) return;
        if ((err as Error).name === 'AbortError') {
          return;
        }
        setState((prev) => ({ ...prev, error: err as Error, loading: false }));
      }
    };

    run();
    const id = window.setInterval(() => {
      controller.abort();
      controller = new AbortController();
      run();
    }, intervalMs);

    return () => {
      active = false;
      controller.abort();
      window.clearInterval(id);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [...deps, refreshKey]);

  return { ...state, refresh };
}
