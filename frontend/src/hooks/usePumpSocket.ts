import { useEffect, useRef } from "react";
import { useQueryClient } from "@tanstack/react-query";

import type { PumpSocketMessage, PumpTelemetry } from "../api/types";
import { useAuthStore } from "../stores/auth";
import { useFuelSaleStore } from "../stores/fuelSale";
import { usePumpsStore } from "../stores/pumps";

const INITIAL_BACKOFF_MS = 1_000;
const MAX_BACKOFF_MS = 30_000;
const HEARTBEAT_MS = 20_000;

function socketUrl(token: string): string {
  const protocol = window.location.protocol === "https:" ? "wss" : "ws";
  return `${protocol}://${window.location.host}/ws/pumps?token=${encodeURIComponent(token)}`;
}

function isTelemetry(value: unknown): value is PumpTelemetry {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<PumpTelemetry>;
  return typeof candidate.pump_id === "string" && typeof candidate.status === "string";
}

function parseMessage(raw: string): PumpSocketMessage | null {
  try {
    const parsed: unknown = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object") return null;
    const type = (parsed as { type?: unknown }).type;
    if (typeof type !== "string") return null;
    return parsed as PumpSocketMessage;
  } catch {
    return null;
  }
}

/**
 * `/ws/pumps` — насосны шууд телеметр.
 *
 * - экспоненциал дахин холболт 1с → 30с
 * - 20 секунд тутам heartbeat
 * - `snapshot` / `pump_status` → pumps store
 * - `fueling_complete` → fuelSale store (төлбөрийн шат руу шилжинэ)
 * - төлөв өөрчлөгдөх бүрд `['pumps']` query-г хүчингүй болгоно
 */
export function usePumpSocket(enabled = true): void {
  const token = useAuthStore((state) => state.token);
  const queryClient = useQueryClient();

  const socketRef = useRef<WebSocket | null>(null);
  const reconnectRef = useRef<number | null>(null);
  const heartbeatRef = useRef<number | null>(null);
  const backoffRef = useRef<number>(INITIAL_BACKOFF_MS);
  const closedByUsRef = useRef<boolean>(false);
  const lastStatusRef = useRef<Record<string, string>>({});

  useEffect(() => {
    const pumpsStore = usePumpsStore.getState();

    if (!enabled || !token) {
      pumpsStore.setConnection("offline");
      return;
    }

    closedByUsRef.current = false;

    const clearTimers = (): void => {
      if (reconnectRef.current !== null) {
        window.clearTimeout(reconnectRef.current);
        reconnectRef.current = null;
      }
      if (heartbeatRef.current !== null) {
        window.clearInterval(heartbeatRef.current);
        heartbeatRef.current = null;
      }
    };

    const invalidatePumps = (): void => {
      void queryClient.invalidateQueries({ queryKey: ["pumps"] });
    };

    const applyTelemetry = (telemetry: PumpTelemetry): void => {
      usePumpsStore.getState().upsert(telemetry);

      const previous = lastStatusRef.current[telemetry.pump_id];
      if (previous !== telemetry.status) {
        lastStatusRef.current[telemetry.pump_id] = telemetry.status;
        invalidatePumps();
      }

      const fuelSale = useFuelSaleStore.getState();
      if (
        fuelSale.authorizationId &&
        telemetry.authorization_id === fuelSale.authorizationId &&
        telemetry.status === "fueling"
      ) {
        fuelSale.tick(telemetry.liters, telemetry.amount, telemetry.flow_lpm);
      }
    };

    const handleMessage = (message: PumpSocketMessage): void => {
      switch (message.type) {
        case "snapshot": {
          const list = Array.isArray(message.pumps) ? message.pumps.filter(isTelemetry) : [];
          usePumpsStore.getState().replaceAll(list);
          for (const item of list) lastStatusRef.current[item.pump_id] = item.status;
          break;
        }
        case "pump_status": {
          if (isTelemetry(message)) applyTelemetry(message);
          break;
        }
        case "fueling_complete": {
          const fuelSale = useFuelSaleStore.getState();
          if (!fuelSale.authorizationId || fuelSale.authorizationId === message.authorization_id) {
            fuelSale.complete(message.liters, message.amount);
          }
          invalidatePumps();
          break;
        }
        case "ping":
        case "error":
        default:
          break;
      }
    };

    const connect = (): void => {
      if (closedByUsRef.current) return;
      usePumpsStore.getState().setConnection("connecting");

      let socket: WebSocket;
      try {
        socket = new WebSocket(socketUrl(token));
      } catch {
        scheduleReconnect();
        return;
      }
      socketRef.current = socket;

      socket.onopen = () => {
        backoffRef.current = INITIAL_BACKOFF_MS;
        usePumpsStore.getState().setConnection("online");
        heartbeatRef.current = window.setInterval(() => {
          if (socket.readyState === WebSocket.OPEN) {
            socket.send(JSON.stringify({ type: "ping" }));
          }
        }, HEARTBEAT_MS);
      };

      socket.onmessage = (event: MessageEvent<string>) => {
        if (typeof event.data !== "string") return;
        const message = parseMessage(event.data);
        if (message) handleMessage(message);
      };

      socket.onerror = () => {
        // onclose үргэлж араас нь дуудагдана — тэнд л дахин холбоно.
      };

      socket.onclose = () => {
        if (heartbeatRef.current !== null) {
          window.clearInterval(heartbeatRef.current);
          heartbeatRef.current = null;
        }
        socketRef.current = null;
        if (closedByUsRef.current) return;
        usePumpsStore.getState().setConnection("offline");
        scheduleReconnect();
      };
    };

    const scheduleReconnect = (): void => {
      if (closedByUsRef.current) return;
      if (reconnectRef.current !== null) return;
      const delay = backoffRef.current;
      backoffRef.current = Math.min(delay * 2, MAX_BACKOFF_MS);
      reconnectRef.current = window.setTimeout(() => {
        reconnectRef.current = null;
        connect();
      }, delay);
    };

    connect();

    return () => {
      closedByUsRef.current = true;
      clearTimers();
      const socket = socketRef.current;
      socketRef.current = null;
      if (socket) {
        socket.onopen = null;
        socket.onmessage = null;
        socket.onerror = null;
        socket.onclose = null;
        if (socket.readyState === WebSocket.OPEN || socket.readyState === WebSocket.CONNECTING) {
          socket.close();
        }
      }
      usePumpsStore.getState().setConnection("offline");
    };
  }, [enabled, token, queryClient]);
}
