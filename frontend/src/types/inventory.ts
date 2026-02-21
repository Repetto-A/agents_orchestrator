export interface Store {
  id: string;
  name: string;
  location?: string;
}

export interface StockProduct {
  product_id: string;
  name?: string;
  current_stock: number;
  price?: number;
  avg_daily_sales: number;
  sales_trend: "increasing" | "decreasing" | "stable";
  estimated_days_left?: number | null;
  is_critical: boolean;
  reorder_qty_suggestion: number;
  safety_stock: number;
  lead_time_days?: number;
}

export interface StockResponse {
  store_id: string;
  products: StockProduct[];
  summary?: {
    total_products: number;
    critical_count: number;
    low_stock_count: number;
  };
}

export interface SalesProduct {
  product_id: string;
  product_name?: string;
  total_sold: number;
  total_revenue: number;
  avg_daily_sales: number;
  weekly_trend: number;
  sales_consistency: number;
  sales_forecast: Record<string, unknown> | null;
}

export interface SalesResponse {
  store_id: string;
  products: SalesProduct[];
  summary?: {
    total_revenue: number;
    avg_daily_sales: number;
    top_product?: SalesProduct;
  };
}

export interface ReportData {
  title: string;
  type: "sales" | "inventory" | "forecast";
  publicUrl?: string;
  downloadUrl?: string;
  generatedAt: string;
  summary?: string;
  kpis?: Record<string, unknown>;
  table?: Array<Record<string, unknown>>;
  data?: Record<string, unknown>;
}

export type ChatIntent = "report" | "sales" | "stock" | "general";

export interface SalesAction {
  id: string;
  label: string;
  type: "discount" | "reserve" | "alternatives" | "checkout";
}

export interface AIResponseMeta {
  planner?: string;
  summarizer?: string;
  cached?: boolean;
  objection_type?: "price" | "timing" | "trust" | "competition" | null;
  stage?: "objection_detected" | "normal_sales";
  actions?: SalesAction[];
  guardrails?: {
    max_discount_percent: number;
    no_fabrication: boolean;
    language: "es" | "en";
  };
  mode?: "seller" | "customer";
  seller_mode?: "auto" | "semi";
  requires_approval?: boolean;
  delivery_mode?: "immediate" | "draft";
  draft_id?: string;
  report_parsed?: boolean;
  purchase_ready?: boolean;
}

export interface ChatMessage {
  id: string;
  type: "user" | "bot";
  content: string;
  intent?: ChatIntent;
  data?: SalesResponse | StockResponse | ReportData;
  publicUrl?: string;
  downloadUrl?: string;
  meta?: AIResponseMeta;
  timestamp: Date;
}

export interface AIQueryResponse {
  agent: string;
  response: string;
  output?: string;
  data?: SalesResponse | StockResponse | ReportData;
  publicUrl?: string;
  downloadUrl?: string;
  conversation_id?: string;
  meta?: AIResponseMeta;
}

export interface ObjectionMetrics {
  store_id: string;
  total_sales_messages: number;
  objections_detected: number;
  resolved_estimate: number;
  by_type: {
    price: number;
    timing: number;
    trust: number;
    competition: number;
  };
}

export interface ConversationMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  intent?: string | null;
  agent?: string | null;
  created_at?: string | null;
}
