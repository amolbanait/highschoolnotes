"use client";

import { useCallback, useEffect, useState } from "react";

import { api, ApiError } from "@/lib/api";
import type { Guide } from "@/lib/types";

export function useGuide(id: string) {
  const [guide, setGuide] = useState<Guide | null>(null);
  const [error, setError] = useState<string | null>(null);

  const reload = useCallback(async () => {
    try {
      setGuide(await api.getGuide(id));
      setError(null);
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not load this guide.");
    }
  }, [id]);

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- loading on mount
    reload();
  }, [reload]);

  return { guide, error, reload };
}
