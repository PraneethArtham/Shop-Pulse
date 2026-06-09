import { useState, useEffect, useCallback } from 'react';

/**
 * Generic fetch hook.
 * @param {Function} fetchFn  — async function returning data
 * @param {Array}    deps     — dependency array (re-fetches when these change)
 * @param {boolean}  skip     — set true to skip the initial fetch
 */
export default function useFetch(fetchFn, deps = [], skip = false) {
  const [data, setData]       = useState(null);
  const [loading, setLoading] = useState(!skip);
  const [error, setError]     = useState(null);

  const run = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const result = await fetchFn();
      setData(result);
    } catch (err) {
      setError(err.response?.data?.detail || err.message || 'Something went wrong');
    } finally {
      setLoading(false);
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    if (!skip) run();
  }, [run, skip]);

  return { data, loading, error, refetch: run };
}
