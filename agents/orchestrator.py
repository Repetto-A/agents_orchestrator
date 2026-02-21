from agents.sales_agent import SalesAgent
from agents.reporting_agent import ReportingAgent
from agents.stock_agent import StockAgent
from config.settings import supabase
from memory.store import get_recent_messages, format_history_for_prompt
from datetime import datetime, timedelta
import re


class Orchestrator:
    """
    Decides which agent should handle the user's request.
    Enriches context with real database data and conversation history.
    """

    def __init__(self, llm):
        self.llm = llm

        self.sales_agent = SalesAgent(
            name="sales_agent",
            llm=llm,
            system_prompt=""  # Sales agent uses its own system prompt in run()
        )

        self.reporting_agent = ReportingAgent(
            name="reporting_agent",
            llm=llm,
            system_prompt="You are a reporting and business intelligence AI. Generate clear, structured reports."
        )

        self.stock_agent = StockAgent(
            name="stock_agent",
            llm=llm,
            system_prompt="You are an inventory management AI. Assess stock risks and provide actionable recommendations."
        )

    @staticmethod
    def _is_llm_error(text: str | None) -> bool:
        value = (text or "").lower()
        return "an error occurred during the llm call" in value or "authentication_error" in value or "invalid x-api-key" in value

    @staticmethod
    def _detect_language(user_input: str) -> str:
        text = (user_input or "").lower()
        spanish_markers = (
            " el ", " la ", " los ", " las ", " de ", " que ", " para ", "con ",
            "inventario", "ventas", "reporte", "resumen", "riesgo", "tienda",
            "quiero", "necesito", "hola", "gracias", "por favor",
            "á", "é", "í", "ó", "ú", "ñ", "¿", "¡",
        )
        padded = f" {text} "
        return "es" if any(marker in padded for marker in spanish_markers) else "en"

    @staticmethod
    def _keyword_intent(user_input: str) -> str:
        text = (user_input or "").lower()
        report_terms = ("report", "kpi", "dashboard", "summary", "analytics", "metric", "table", "reporte", "resumen", "métrica", "metrica", "tablero")
        stock_terms = ("stock", "inventory", "reorder", "safety", "cover", "days left", "critical", "risk", "inventario", "reabastecer", "stock bajo", "riesgo", "cobertura", "crítico", "critico")
        if any(term in text for term in stock_terms):
            return "stock_agent"
        if any(term in text for term in report_terms):
            return "reporting_agent"
        return "sales_agent"

    def _fallback_stock_response(self, store_id: str | None, lang: str = "en") -> dict:
        if not store_id:
            message = (
                "Modo de respaldo: selecciona una tienda primero para analizar el riesgo de inventario con datos reales."
                if lang == "es"
                else "Fallback mode: select a store first so I can analyze stock risk from live data."
            )
            return {"agent": "stock_agent", "response": message, "output": message, "data": None, "publicUrl": None, "downloadUrl": None, "meta": {"fallback": True, "reason": "missing_store_id"}}

        result = supabase.table("products").select("id,name,current_stock,avg_daily_sales,safety_stock,lead_time_days").eq("store_id", store_id).execute()
        products = result.data or []
        if not products:
            message = (
                f"Modo de respaldo: no encontré productos para la tienda `{store_id}`."
                if lang == "es"
                else f"Fallback mode: I found no products for store `{store_id}`."
            )
            return {"agent": "stock_agent", "response": message, "output": message, "data": None, "publicUrl": None, "downloadUrl": None, "meta": {"fallback": True, "reason": "no_products"}}

        risks = []
        for p in products:
            avg = float(p.get("avg_daily_sales") or 0.0)
            stock = float(p.get("current_stock") or 0.0)
            days_left = round(stock / avg, 1) if avg > 0 else None
            risks.append({
                "id": p.get("id"),
                "name": p.get("name"),
                "current_stock": stock,
                "avg_daily_sales": avg,
                "days_left": days_left,
                "critical": days_left is not None and days_left <= 7,
            })

        critical = [r for r in risks if r["critical"]]
        low = [r for r in risks if r["days_left"] is not None and r["days_left"] <= 30]
        ordered = sorted(
            risks,
            key=lambda item: item["days_left"] if item["days_left"] is not None else float("inf"),
        )
        top = ordered[:3]

        if lang == "es":
            lines = [
                f"Modo de respaldo (LLM no disponible) para `{store_id}`: {len(critical)} productos críticos y {len(low)} con stock bajo.",
                "Productos con mayor riesgo:",
            ]
        else:
            lines = [
                f"Fallback mode (LLM unavailable) for `{store_id}`: {len(critical)} critical and {len(low)} low-stock products.",
                "Top risk items:",
            ]
        for item in top:
            if item["days_left"] is None:
                lines.append(f"- {item['name']}: sin velocidad de ventas disponible" if lang == "es" else f"- {item['name']}: no sales velocity data")
            else:
                lines.append(
                    f"- {item['name']}: {item['days_left']} días restantes (stock {int(item['current_stock'])}, prom/día {item['avg_daily_sales']:.1f})"
                    if lang == "es"
                    else f"- {item['name']}: {item['days_left']} days left (stock {int(item['current_stock'])}, avg/day {item['avg_daily_sales']:.1f})"
                )

        message = "\n".join(lines)
        data = {
            "store_id": store_id,
            "summary": {
                "total_products": len(risks),
                "critical_count": len(critical),
                "low_stock_count": len(low),
            },
            "top_risks": top,
        }
        return {"agent": "stock_agent", "response": message, "output": message, "data": data, "publicUrl": None, "downloadUrl": None, "meta": {"fallback": True, "reason": "llm_unavailable"}}

    def _fallback_sales_response(self, store_id: str | None, lang: str = "en") -> dict:
        if not store_id:
            message = (
                "Modo de respaldo: selecciona una tienda primero para resumir ventas con datos reales."
                if lang == "es"
                else "Fallback mode: select a store first so I can summarize sales from live data."
            )
            return {"agent": "sales_agent", "response": message, "output": message, "data": None, "publicUrl": None, "downloadUrl": None, "meta": {"fallback": True, "reason": "missing_store_id"}}

        seven_days_ago = (datetime.utcnow().date() - timedelta(days=7)).isoformat()
        sales_result = (
            supabase.table("sales_history")
            .select("product_id, quantity, total_amount")
            .eq("store_id", store_id)
            .gte("sale_date", seven_days_ago)
            .execute()
        )
        products_result = supabase.table("products").select("id, name").eq("store_id", store_id).execute()
        product_names = {p["id"]: p["name"] for p in (products_result.data or [])}

        agg = {}
        for sale in (sales_result.data or []):
            pid = sale["product_id"]
            if pid not in agg:
                agg[pid] = {"qty": 0, "revenue": 0.0}
            agg[pid]["qty"] += int(sale.get("quantity") or 0)
            agg[pid]["revenue"] += float(sale.get("total_amount") or 0.0)

        if not agg:
            message = (
                f"Modo de respaldo: no encontré ventas en los últimos 7 días para `{store_id}`."
                if lang == "es"
                else f"Fallback mode: no sales records found in the last 7 days for `{store_id}`."
            )
            return {"agent": "sales_agent", "response": message, "output": message, "data": {"store_id": store_id, "products": [], "summary": None}, "publicUrl": None, "downloadUrl": None, "meta": {"fallback": True, "reason": "no_sales_data"}}

        ordered = sorted(agg.items(), key=lambda item: item[1]["revenue"], reverse=True)
        top = ordered[:3]
        total_revenue = round(sum(item[1]["revenue"] for item in ordered), 2)
        total_qty = sum(item[1]["qty"] for item in ordered)

        lines = (
            [f"Modo de respaldo (LLM no disponible) para `{store_id}`: ingresos últimos 7 días ${total_revenue:.2f}, unidades vendidas {total_qty}.", "Productos con mejor desempeño:"]
            if lang == "es"
            else [f"Fallback mode (LLM unavailable) for `{store_id}`: last 7 days revenue ${total_revenue:.2f}, units sold {total_qty}.", "Top performers:"]
        )
        for pid, item in top:
            lines.append(f"- {product_names.get(pid, pid)}: {item['qty']} units, ${item['revenue']:.2f}")

        message = "\n".join(lines)
        data_products = [
            {"product_id": pid, "product_name": product_names.get(pid, pid), "total_sold": item["qty"], "total_revenue": round(item["revenue"], 2)}
            for pid, item in ordered
        ]
        data = {"store_id": store_id, "products": data_products, "summary": {"total_revenue": total_revenue, "total_units_sold": total_qty}}
        return {"agent": "sales_agent", "response": message, "output": message, "data": data, "publicUrl": None, "downloadUrl": None, "meta": {"fallback": True, "reason": "llm_unavailable"}}

    def _fallback_reporting_response(self, store_id: str | None, lang: str = "en") -> dict:
        stock = self._fallback_stock_response(store_id, lang=lang)
        sales = self._fallback_sales_response(store_id, lang=lang)
        stock_summary = (stock.get("data") or {}).get("summary") if stock.get("data") else None
        sales_summary = (sales.get("data") or {}).get("summary") if sales.get("data") else None

        lines = ["Reporte en modo de respaldo (LLM no disponible):"] if lang == "es" else ["Fallback report (LLM unavailable):"]
        if sales_summary:
            lines.append(f"- Ingresos (7d): ${sales_summary.get('total_revenue', 0):.2f}" if lang == "es" else f"- Revenue (7d): ${sales_summary.get('total_revenue', 0):.2f}")
            lines.append(f"- Unidades vendidas (7d): {sales_summary.get('total_units_sold', 0)}" if lang == "es" else f"- Units sold (7d): {sales_summary.get('total_units_sold', 0)}")
        if stock_summary:
            lines.append(f"- Productos: {stock_summary.get('total_products', 0)}" if lang == "es" else f"- Products: {stock_summary.get('total_products', 0)}")
            lines.append(f"- Stock crítico: {stock_summary.get('critical_count', 0)}" if lang == "es" else f"- Critical stock: {stock_summary.get('critical_count', 0)}")
            lines.append(f"- Stock bajo: {stock_summary.get('low_stock_count', 0)}" if lang == "es" else f"- Low stock: {stock_summary.get('low_stock_count', 0)}")

        message = "\n".join(lines)
        data = {"store_id": store_id, "sales_summary": sales_summary, "stock_summary": stock_summary}
        return {"agent": "reporting_agent", "response": message, "output": message, "data": data, "publicUrl": None, "downloadUrl": None, "meta": {"fallback": True, "reason": "llm_unavailable"}}

    def _fallback_response(self, user_input: str, store_id: str | None) -> dict:
        lang = self._detect_language(user_input)
        intent = self._keyword_intent(user_input)
        if intent == "stock_agent":
            return self._fallback_stock_response(store_id, lang=lang)
        if intent == "reporting_agent":
            return self._fallback_reporting_response(store_id, lang=lang)
        return self._fallback_sales_response(store_id, lang=lang)

    @staticmethod
    def _extract_terms(user_input: str) -> list[str]:
        tokens = re.findall(r"[a-zA-Z0-9-]+", (user_input or "").lower())
        stop = {
            "the", "a", "an", "and", "or", "to", "for", "with", "about", "this", "that",
            "que", "con", "para", "por", "una", "uno", "los", "las", "del", "sobre",
        }
        return [token for token in tokens if len(token) > 2 and token not in stop]

    def _pick_relevant_products(self, products: list[dict], user_input: str) -> list[dict]:
        if not products:
            return []

        terms = self._extract_terms(user_input)
        matched = []
        for product in products:
            text = f"{product.get('id', '')} {product.get('name', '')}".lower()
            if any(term in text for term in terms):
                matched.append(product)

        if matched:
            return matched[:5]

        # Intent-aware fallback selection when there is no direct name match.
        intent = self._keyword_intent(user_input)
        if intent == "stock_agent":
            ordered = sorted(
                products,
                key=lambda p: ((p.get("current_stock") or 0) / (p.get("avg_daily_sales") or 1)) if (p.get("avg_daily_sales") or 0) > 0 else 9999,
            )
            return ordered[:5]
        if intent == "reporting_agent":
            return products[:5]

        # Sales: prefer products with available stock and lower price point.
        ordered = sorted(products, key=lambda p: (p.get("price") or 0))
        return ordered[:5]

    def _get_initial_user_question(self, conversation_id: str | None, fallback_user_input: str) -> str:
        if not conversation_id:
            return fallback_user_input

        result = (
            supabase.table("messages")
            .select("content")
            .eq("conversation_id", conversation_id)
            .eq("role", "user")
            .order("created_at", desc=False)
            .limit(1)
            .execute()
        )
        rows = result.data or []
        if not rows:
            return fallback_user_input
        return rows[0].get("content") or fallback_user_input

    def _build_relevant_context(self, store_id: str | None, user_input: str, conversation_id: str | None = None) -> str:
        """Build a compact conversation package with initial question, memory, DB data and response rules."""
        parts = []
        initial_question = self._get_initial_user_question(conversation_id, user_input)
        parts.append("## INITIAL USER QUESTION")
        parts.append(initial_question)

        # 1) Relevant product + sales snapshot for current store.
        if store_id:
            products_result = (
                supabase.table("products")
                .select("id,name,price,current_stock,avg_daily_sales,safety_stock,lead_time_days")
                .eq("store_id", store_id)
                .execute()
            )
            products = products_result.data or []
            relevant_products = self._pick_relevant_products(products, user_input)

            if relevant_products:
                parts.append("## RELEVANT PRODUCTS (store context)")
                for product in relevant_products:
                    avg = product.get("avg_daily_sales") or 0
                    stock = product.get("current_stock") or 0
                    days_left = round(stock / avg, 1) if avg > 0 else "N/A"
                    parts.append(
                        f"- {product.get('name')} (ID: {product.get('id')}): ${float(product.get('price') or 0):.2f} | "
                        f"Stock: {stock} | Avg/day: {avg} | Days left: {days_left}"
                    )

            seven_days_ago = (datetime.utcnow().date() - timedelta(days=7)).isoformat()
            sales_query = (
                supabase.table("sales_history")
                .select("product_id, quantity, total_amount")
                .eq("store_id", store_id)
                .gte("sale_date", seven_days_ago)
            )
            relevant_ids = [p.get("id") for p in relevant_products if p.get("id")]
            if relevant_ids:
                sales_query = sales_query.in_("product_id", relevant_ids)
            sales_result = sales_query.execute()

            if sales_result.data:
                product_names = {p["id"]: p["name"] for p in products}
                sales_by_product = {}
                for sale in sales_result.data:
                    pid = sale["product_id"]
                    if pid not in sales_by_product:
                        sales_by_product[pid] = {"qty": 0, "revenue": 0}
                    sales_by_product[pid]["qty"] += sale["quantity"]
                    sales_by_product[pid]["revenue"] += sale["total_amount"]

                parts.append("\n## LAST 7 DAYS SALES (relevant scope)")
                for pid, agg in sorted(sales_by_product.items(), key=lambda row: row[1]["revenue"], reverse=True)[:5]:
                    name = product_names.get(pid, pid)
                    parts.append(f"- {name}: {agg['qty']} units sold, ${agg['revenue']:.2f} revenue")

        # 2) Conversation memory (short and recent).
        if conversation_id:
            messages = get_recent_messages(conversation_id, limit=8)
            if messages:
                parts.append("\n## CONVERSATION CONTEXT (recent)")
                parts.append(format_history_for_prompt(messages))
            else:
                parts.append("\n## CONVERSATION CONTEXT (recent)")
                parts.append("No previous turns yet.")
        else:
            parts.append("\n## CONVERSATION CONTEXT (recent)")
            parts.append("No previous turns yet.")

        parts.append("\n## CURRENT USER QUESTION")
        parts.append(user_input)

        parts.append("\n## RESPONSE RULES")
        parts.append("- Continue the conversation naturally (do not restart context).")
        parts.append("- Answer the current user question directly.")
        parts.append("- Use only the relevant DB info shown above; do not invent data.")
        parts.append("- Keep the response concise and actionable.")
        parts.append("- Respond in the same language as the user.")

        return "\n".join(parts) if parts else "No relevant data available."

    def route(self, user_input: str, context: str = None, store_id: str = None, conversation_id: str = None, forced_agent: str | None = None):
        # Build compact, relevant context from DB + memory.
        rich_context = self._build_relevant_context(store_id, user_input, conversation_id)

        # Combine with any additional context passed from the API
        if context:
            rich_context = f"{context}\n\n{rich_context}"

        if forced_agent == "sales_agent":
            result = self.sales_agent.run(user_input, rich_context)
            return result if not self._is_llm_error(result.get("response")) else self._fallback_sales_response(store_id, lang=self._detect_language(user_input))

        # Route decision
        decision_prompt = f"""You are an AI orchestrator.

Your task is to decide which agent should handle the user's request.

Agents:
- sales_agent: product inquiries, buying questions, pricing, objections, persuasion, recommendations, ANY customer-facing sales conversation
- reporting_agent: structured reports, KPIs, tables, summaries, analytics
- stock_agent: inventory risk, stock levels, replenishment or transfer suggestions

User request:
"{user_input}"

Respond with ONLY one of the following values:
- sales_agent
- reporting_agent
- stock_agent"""

        decision_raw = self.llm(decision_prompt)
        decision = (decision_raw or "").strip()

        if self._is_llm_error(decision):
            return self._fallback_response(user_input=user_input, store_id=store_id)

        d = decision.lower()

        # Match agent
        if d in ("sales_agent", "sales") or "sales" in d:
            result = self.sales_agent.run(user_input, rich_context)
            return result if not self._is_llm_error(result.get("response")) else self._fallback_sales_response(store_id, lang=self._detect_language(user_input))

        if d in ("reporting_agent", "report", "report_agent") or "report" in d:
            result = self.reporting_agent.run(user_input, rich_context)
            return result if not self._is_llm_error(result.get("response")) else self._fallback_reporting_response(store_id, lang=self._detect_language(user_input))

        if d in ("stock_agent", "stock", "inventory_agent", "inventory") or "stock" in d or "inventory" in d:
            result = self.stock_agent.run(user_input, rich_context)
            return result if not self._is_llm_error(result.get("response")) else self._fallback_stock_response(store_id, lang=self._detect_language(user_input))

        # Fallback to sales agent (most common use case)
        result = self.sales_agent.run(user_input, rich_context)
        return result if not self._is_llm_error(result.get("response")) else self._fallback_response(user_input=user_input, store_id=store_id)
