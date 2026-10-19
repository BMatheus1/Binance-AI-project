"use client";

import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { apiGet, bootstrapSession, dashboardSocket } from "@/lib/api";
import type { DashboardSnapshot, OverviewData } from "@/lib/types";

interface DashboardContextValue {
  snapshot: DashboardSnapshot | null;
  connected: boolean;
  loading: boolean;
  error: string | null;
  refresh: () => Promise<void>;
}

const DashboardContext = createContext<DashboardContextValue | null>(null);

export function DashboardProvider({ children }: { children: React.ReactNode }) {
  const [snapshot, setSnapshot] = useState<DashboardSnapshot | null>(null);
  const [connected, setConnected] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const retry = useRef<ReturnType<typeof setTimeout> | null>(null);

  const refresh = useCallback(async () => {
    try {
      const overview = await apiGet<OverviewData>("/api/overview");
      setSnapshot((current) => ({
        overview,
        markets: current?.markets ?? {},
        health: current?.health ?? {},
      }));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Falha desconhecida");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let disposed = false;
    let socket: WebSocket | null = null;
    const connect = async () => {
      try {
        const csrf = await bootstrapSession();
        if (disposed) return;
        socket = dashboardSocket(csrf);
        socket.onopen = () => setConnected(true);
        socket.onmessage = (event) => {
          const payload = JSON.parse(event.data);
          if (payload.type === "snapshot") {
            setSnapshot(payload.data);
            setError(null);
            setLoading(false);
          }
        };
        socket.onerror = () => setError("Canal em tempo real indisponível");
        socket.onclose = () => {
          setConnected(false);
          if (!disposed) retry.current = setTimeout(connect, 2500);
        };
      } catch (cause) {
        setError(cause instanceof Error ? cause.message : "Backend indisponível");
        setLoading(false);
        if (!disposed) retry.current = setTimeout(connect, 3000);
      }
    };
    connect();
    return () => {
      disposed = true;
      if (retry.current) clearTimeout(retry.current);
      socket?.close();
    };
  }, []);

  const value = useMemo(() => ({ snapshot, connected, loading, error, refresh }),
                        [snapshot, connected, loading, error, refresh]);
  return <DashboardContext.Provider value={value}>{children}</DashboardContext.Provider>;
}

export function useDashboard() {
  const context = useContext(DashboardContext);
  if (!context) throw new Error("useDashboard precisa de DashboardProvider");
  return context;
}

export function useApiData<T>(path: string, refreshMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const load = useCallback(async () => {
    try {
      setData(await apiGet<T>(path));
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Falha desconhecida");
    } finally {
      setLoading(false);
    }
  }, [path]);
  useEffect(() => {
    load();
    if (!refreshMs) return;
    const timer = setInterval(load, refreshMs);
    return () => clearInterval(timer);
  }, [load, refreshMs]);
  return { data, error, loading, reload: load };
}
