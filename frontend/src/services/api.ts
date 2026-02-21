import { AIQueryResponse, ConversationMessage, ObjectionMetrics, StockResponse, SalesResponse, Store } from "@/types/inventory";

const rawApiBaseUrl = import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";
const API_BASE_URL = String(rawApiBaseUrl).trim().replace(/\/+$/, "");

type QueryParams = Record<string, string | number | boolean | null | undefined>;

// Convert camelCase to snake_case for API params
function toSnakeCase(obj: QueryParams): QueryParams {
  const result: QueryParams = {};
  for (const key in obj) {
    const snakeKey = key.replace(/[A-Z]/g, (letter) => `_${letter.toLowerCase()}`);
    result[snakeKey] = obj[key];
  }
  return result;
}

// Generic fetch wrapper with snake_case conversion
async function apiFetch<T>(
  endpoint: string,
  options: RequestInit = {},
  queryParams?: QueryParams
): Promise<T> {
  const normalizedEndpoint = endpoint.trim().startsWith("/") ? endpoint.trim() : `/${endpoint.trim()}`;
  let url = `${API_BASE_URL}${normalizedEndpoint}`;

  if (queryParams) {
    const snakeParams = toSnakeCase(queryParams);
    const searchParams = new URLSearchParams();
    Object.entries(snakeParams).forEach(([key, value]) => {
      if (value !== undefined && value !== null) {
        searchParams.append(key, String(value));
      }
    });
    url += `?${searchParams.toString()}`;
  }

  const response = await fetch(url, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...options.headers,
    },
  });

  if (!response.ok) {
    throw new Error(`API Error: ${response.status} ${response.statusText}`);
  }

  return response.json();
}

// AI Orchestrator
export async function orchestrate(
  message: string,
  storeId: string,
  conversationId?: string,
  mode: "seller" | "customer" = "seller",
  sellerMode: "auto" | "semi" = "semi",
  delivery: "immediate" | "draft" = "immediate"
): Promise<AIQueryResponse> {
  return apiFetch<AIQueryResponse>("/ai/query", {
    method: "POST",
    body: JSON.stringify({
      message,
      store_id: storeId,
      conversation_id: conversationId,
      context: `Current store: ${storeId}`,
      mode,
      seller_mode: sellerMode,
      delivery,
    }),
  });
}


// Normalize backend agent names to frontend intents
export function normalizeIntent(agent: string): "report" | "sales" | "stock" | "general" {
  const mapping: Record<string, "report" | "sales" | "stock" | "general"> = {
    sales_agent: "sales",
    reporting_agent: "report",
    stock_agent: "stock",
  };
  return mapping[agent] || "general";
}

// Inventory/Stock endpoints
export async function getStockAvailability(storeId: string): Promise<StockResponse> {
  return apiFetch<StockResponse>("/inventory/stock", {}, { storeId });
}

export async function getInventoryItems(storeId: string): Promise<StockResponse> {
  return apiFetch<StockResponse>("/inventory/items", {}, { storeId });
}

// Sales endpoints
export async function getSalesOverview(storeId: string): Promise<SalesResponse> {
  return apiFetch<SalesResponse>("/sales/overview", {}, { storeId });
}

export async function getObjectionMetrics(storeId: string): Promise<ObjectionMetrics> {
  return apiFetch<ObjectionMetrics>("/sales/objections/metrics", {}, { storeId });
}

export async function getConversationMessages(
  conversationId: string,
  limit = 30,
  viewerMode: "seller" | "customer" = "seller"
): Promise<ConversationMessage[]> {
  return apiFetch<ConversationMessage[]>("/ai/conversation/messages", {}, { conversationId, limit, viewerMode });
}

export async function setConversationMode(conversationId: string, sellerMode: "auto" | "semi"): Promise<{ conversation_id: string; seller_mode: "auto" | "semi" }> {
  return apiFetch("/ai/conversation/mode", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: conversationId,
      seller_mode: sellerMode,
    }),
  });
}

export async function getConversationMode(conversationId: string): Promise<{ conversation_id: string; seller_mode: "auto" | "semi" }> {
  return apiFetch("/ai/conversation/mode", {}, { conversationId });
}

export async function sendSellerDraft(conversationId: string, replyText: string, draftId?: string): Promise<{ ok: boolean }> {
  return apiFetch("/ai/seller/send-draft", {
    method: "POST",
    body: JSON.stringify({
      conversation_id: conversationId,
      reply_text: replyText,
      draft_id: draftId,
    }),
  });
}

export interface CheckoutSimulateRequest {
  conversation_id: string;
  store_id?: string;
  customer_name: string;
  email: string;
  address: string;
  payment_method: "credit_card" | "debit_card" | "bank_transfer" | "cash_on_delivery";
}

export interface CheckoutSimulateResponse {
  ok: boolean;
  payment_id?: string;
  payment_url?: string;
  email_sent?: boolean;
  email_error?: string | null;
  error?: string;
}

export async function simulateCheckout(payload: CheckoutSimulateRequest): Promise<CheckoutSimulateResponse> {
  return apiFetch<CheckoutSimulateResponse>("/ai/checkout/simulate", {
    method: "POST",
    body: JSON.stringify(payload),
  });
}

// Stores endpoint
export async function getStores(): Promise<Store[]> {
  try {
    const data = await apiFetch<Store[]>("/stores");
    console.log("getStores API response:", data);
    return data;
  } catch (error) {
    console.error("getStores error:", error);
    throw error;
  }
}

