from fastapi import APIRouter
from pydantic import BaseModel
from config.settings import get_llm, supabase
from memory.store import get_or_create_conversation, save_message
from typing import List, Optional
from datetime import datetime, timedelta
import json
import re
import traceback
import os
import smtplib
from email.message import EmailMessage

router = APIRouter(prefix="/ai", tags=["AI"])


class AIRequest(BaseModel):
    message: str
    context: str | None = None
    conversation_id: str | None = None
    store_id: str | None = None
    mode: str | None = "seller"
    seller_mode: str | None = "semi"
    delivery: str | None = "immediate"


class ConversationMessageResponse(BaseModel):
    id: str
    role: str
    content: str
    intent: Optional[str] = None
    agent: Optional[str] = None
    created_at: Optional[str] = None


OBJECTION_TYPES = ("price", "timing", "trust", "competition")
PAYMENT_METHODS = ("credit_card", "debit_card", "bank_transfer", "cash_on_delivery")


def _detect_language(text: str) -> str:
    value = (text or "").lower()
    markers_es = (" inventario ", " ventas ", " reporte ", " precio ", " tienda ", " quiero ", " necesito ", " por favor ", "¿", "¡", "ñ")
    padded = f" {value} "
    return "es" if any(marker in padded for marker in markers_es) else "en"


def _classify_objection(text: str) -> str | None:
    value = (text or "").lower()

    patterns = {
        "price": ("expensive", "price", "discount", "budget", "caro", "precio", "descuento", "barato"),
        "timing": ("not now", "later", "think about", "tomorrow", "ahora no", "despues", "luego", "pensar"),
        "trust": ("trust", "reliable", "guarantee", "warranty", "confianza", "seguro", "garantia"),
        "competition": ("competitor", "alternative", "other brand", "amazon", "competencia", "alternativa", "otra tienda"),
    }

    for objection_type, keywords in patterns.items():
        if any(keyword in value for keyword in keywords):
            return objection_type
    return None


def _detect_purchase_intent(text: str) -> bool:
    value = (text or "").lower()
    keywords = (
        "i'll buy",
        "i will buy",
        "i want to buy",
        "buy it",
        "purchase",
        "checkout",
        "confirm purchase",
        "i confirm",
        "quiero comprar",
        "lo compro",
        "comprar",
        "proceder",
        "pagar",
        "confirmo",
        "confirmar compra",
        "confirmar la compra",
        "si confirmo",
        "sí confirmo",
    )
    return any(keyword in value for keyword in keywords)


def _is_affirmative_reply(text: str) -> bool:
    value = (text or "").strip().lower()
    if not value:
        return False
    normalized = re.sub(r"[^\wáéíóúüñ]+", " ", value).strip()
    short_yes = {
        "si",
        "sí",
        "yes",
        "ok",
        "okay",
        "dale",
        "de una",
        "va",
        "listo",
        "perfecto",
        "confirmo",
    }
    if normalized in short_yes:
        return True
    # Demo-friendly: treat very short positive confirmations as purchase-ready.
    return len(normalized) <= 12 and any(token in normalized for token in ("si", "sí", "yes", "ok", "dale", "confirmo"))


def _response_confirms_purchase(text: str) -> bool:
    value = (text or "").lower()
    markers = (
        "would you like to proceed",
        "ready to proceed",
        "confirm your purchase",
        "purchase confirmed",
        "order confirmed",
        "proceed to payment",
        "quieres proceder",
        "listo para proceder",
        "confirmar tu compra",
        "confirmas la compra",
        "pedido confirmado",
        "tu pedido está confirmado",
        "tu pedido esta confirmado",
        "pasar al pago",
        "ir al pago",
    )
    return any(marker in value for marker in markers)


def _llm_checkout_signal(
    llm_callable,
    user_message: str,
    assistant_message: str,
    language: str,
) -> dict | None:
    """Use the LLM as a purchase-intent judge to avoid brittle keyword-only logic."""
    if not llm_callable:
        return None

    system_prompt = (
        "You are a strict purchase-intent classifier. "
        "Return ONLY valid JSON with keys: purchase_confirmed (bool), confidence (0..1), reason (string). "
        "Set purchase_confirmed=true only if the customer is clearly confirming they want to proceed to checkout now."
    )
    prompt = (
        f"Language: {language}\n"
        f"Customer message: {user_message}\n"
        f"Assistant message: {assistant_message}\n\n"
        "Classify if checkout should be enabled now."
    )
    try:
        raw = llm_callable(prompt, system_prompt)
        start = raw.find("{")
        end = raw.rfind("}")
        if start == -1 or end == -1 or end <= start:
            return None
        parsed = json.loads(raw[start : end + 1])
        return {
            "purchase_confirmed": bool(parsed.get("purchase_confirmed")),
            "confidence": float(parsed.get("confidence", 0.0)),
            "reason": str(parsed.get("reason", ""))[:300],
        }
    except Exception:
        return None


def _build_sales_actions(language: str, objection_type: str | None) -> list[dict]:
    if language == "es":
        actions = [
            {"id": "reserve_item", "label": "Reservar producto", "type": "reserve"},
            {"id": "show_alternatives", "label": "Ver alternativas", "type": "alternatives"},
        ]
        if objection_type == "price":
            actions.insert(0, {"id": "apply_discount_10", "label": "Aplicar 10% desc.", "type": "discount"})
        return actions

    actions = [
        {"id": "reserve_item", "label": "Reserve item", "type": "reserve"},
        {"id": "show_alternatives", "label": "Show alternatives", "type": "alternatives"},
    ]
    if objection_type == "price":
        actions.insert(0, {"id": "apply_discount_10", "label": "Apply 10% discount", "type": "discount"})
    return actions


def _safe_discount_guardrail(text: str, language: str) -> str:
    response = text or ""
    return re.sub(r"\b([2-9]\d)\s*%", "20%", response)


def _is_discount_allowed(seller_mode: str, objection_type: str | None) -> bool:
    return seller_mode == "semi" and objection_type == "price"


def _remove_discount_mentions(text: str) -> str:
    raw = text or ""
    if not raw:
        return raw

    chunks = [chunk.strip() for chunk in re.split(r"(?:\n+|(?<=[.!?])\s+)", raw) if chunk.strip()]
    filtered: list[str] = []
    for chunk in chunks:
        lower = chunk.lower()
        has_discount_term = any(term in lower for term in ("discount", "descuento", "rebaja", "off"))
        has_percent_offer = bool(re.search(r"\b\d{1,2}\s*%", chunk))
        if has_discount_term or has_percent_offer:
            continue
        filtered.append(chunk)

    return " ".join(filtered).strip() or raw


def _send_checkout_email(to_email: str, customer_name: str, payment_url: str, language: str) -> tuple[bool, str | None]:
    smtp_host = os.getenv("SMTP_HOST")
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    smtp_from = os.getenv("SMTP_FROM") or smtp_user
    smtp_port = int(os.getenv("SMTP_PORT", "587"))

    if not smtp_host or not smtp_user or not smtp_pass or not smtp_from:
        return False, "SMTP not configured"

    msg = EmailMessage()
    msg["From"] = smtp_from
    msg["To"] = to_email
    if language == "es":
        msg["Subject"] = "Pago pendiente - Cruisely Demo"
        msg.set_content(
            f"Hola {customer_name},\n\n"
            f"Tu compra simulada fue registrada correctamente.\n"
            f"Podés completar el pago en este enlace de demo:\n{payment_url}\n\n"
            "Este es un flujo de demostración (sin cobro real).\n"
        )
    else:
        msg["Subject"] = "Payment pending - Cruisely Demo"
        msg.set_content(
            f"Hi {customer_name},\n\n"
            f"Your simulated purchase was registered successfully.\n"
            f"You can complete payment at this demo link:\n{payment_url}\n\n"
            "This is a demo flow (no real charge).\n"
        )

    try:
        with smtplib.SMTP(smtp_host, smtp_port, timeout=10) as server:
            server.starttls()
            server.login(smtp_user, smtp_pass)
            server.send_message(msg)
        return True, None
    except Exception as exc:
        return False, str(exc)


def _extract_report_payload(text: str) -> tuple[str, dict | None]:
    raw = text or ""
    marker = "REPORT_JSON:"
    if marker in raw:
        conversational, payload = raw.split(marker, 1)
        conversational = conversational.strip()
        payload = payload.strip()
        try:
            return conversational or "Here is your report.", json.loads(payload)
        except Exception:
            return raw, None

    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        maybe_json = raw[start : end + 1]
        try:
            parsed = json.loads(maybe_json)
            conversational = raw[:start].strip() or "Here is your report."
            return conversational, parsed
        except Exception:
            return raw, None

    return raw, None


def _get_store_sales_snapshot(store_id: str | None) -> dict | None:
    if not store_id:
        return None

    products_result = supabase.table("products").select("id,name,price,current_stock").eq("store_id", store_id).execute()
    products = products_result.data or []
    if not products:
        return None

    cheapest = min(products, key=lambda row: row.get("price") or 0)

    seven_days_ago = (datetime.utcnow().date() - timedelta(days=7)).isoformat()
    sales_result = (
        supabase.table("sales_history")
        .select("product_id, quantity")
        .eq("store_id", store_id)
        .gte("sale_date", seven_days_ago)
        .execute()
    )

    sold_by_product = {}
    for sale in (sales_result.data or []):
        pid = sale["product_id"]
        sold_by_product[pid] = sold_by_product.get(pid, 0) + int(sale.get("quantity") or 0)

    top_product = None
    if sold_by_product:
        best_id = max(sold_by_product, key=sold_by_product.get)
        product_lookup = {p["id"]: p for p in products}
        top_product = product_lookup.get(best_id, {"id": best_id, "name": best_id})
        top_product["units"] = sold_by_product.get(best_id, 0)

    return {"cheapest": cheapest, "top_product": top_product}


def _build_objection_tip(objection_type: str, language: str, snapshot: dict | None, allow_discount: bool) -> str:
    cheapest = (snapshot or {}).get("cheapest")
    top = (snapshot or {}).get("top_product")

    if language == "es":
        tips = {
            "price": (
                f"Tip de cierre: podés ofrecer descuento opcional (10-15% máx.) y mencionar una alternativa económica como {cheapest.get('name')} (${cheapest.get('price'):.2f})."
                if allow_discount and cheapest
                else "Tip de cierre: reforzá valor/ROI y compará con una alternativa más económica."
            ),
            "timing": "Tip de cierre: usa urgencia suave y ofrece reservar el producto hoy.",
            "trust": f"Tip de cierre: refuerza prueba social con top seller ({top.get('name')} - {top.get('units')} unidades en 7 días)." if top else "Tip de cierre: refuerza garantías y confianza de clientes.",
            "competition": f"Tip de cierre: compara valor y propone alternativa relevante como {top.get('name')}." if top else "Tip de cierre: compara valor y ofrece una alternativa de mejor ajuste.",
        }
        return tips.get(objection_type, "")

    tips = {
        "price": (
            f"Closing tip: you may optionally offer up to 10-15% and mention a budget option like {cheapest.get('name')} (${cheapest.get('price'):.2f})."
            if allow_discount and cheapest
            else "Closing tip: reinforce ROI/value and compare with a lower-price alternative."
        ),
        "timing": "Closing tip: use gentle urgency and offer to reserve the item today.",
        "trust": f"Closing tip: use social proof with a top seller ({top.get('name')} - {top.get('units')} units in 7 days)." if top else "Closing tip: reinforce warranty and customer trust.",
        "competition": f"Closing tip: compare value and suggest an alternative like {top.get('name')}." if top else "Closing tip: compare value and suggest a better-fit alternative.",
    }
    return tips.get(objection_type, "")


def _normalize_seller_mode(value: str | None) -> str:
    v = (value or "semi").lower()
    return "semi" if v == "semi" else "auto"


def _conversation_status_for_mode(seller_mode: str) -> str:
    return f"active_{_normalize_seller_mode(seller_mode)}"


def _seller_mode_from_status(status: str | None) -> str:
    value = (status or "").lower()
    if value in ("", "active"):
        return "semi"
    if value.endswith("_semi"):
        return "semi"
    return "auto"


def _get_seller_mode_from_conversation(conversation_id: str | None) -> str:
    if not conversation_id:
        return "semi"
    result = supabase.table("conversations").select("status").eq("id", conversation_id).limit(1).execute()
    if not result.data:
        return "semi"
    return _seller_mode_from_status(result.data[0].get("status"))


@router.post("/query")
async def query_ai(request: AIRequest):
    try:
        from agents.orchestrator import Orchestrator

        llm = get_llm()
        orchestrator = Orchestrator(llm)

        # Extract store_id from context or request
        store_id = request.store_id
        if not store_id and request.context:
            for line in request.context.split("\n"):
                if "store" in line.lower() and ":" in line:
                    parts = line.split(":")
                    candidate = parts[-1].strip()
                    if candidate.startswith("store-"):
                        store_id = candidate
                        break

        # Get or create conversation
        conversation_id = get_or_create_conversation(
            store_id=store_id or "unknown",
            conversation_id=request.conversation_id,
        )

        mode = (request.mode or "seller").lower()
        requested_seller_mode = _normalize_seller_mode(request.seller_mode)
        conversation_seller_mode = _get_seller_mode_from_conversation(conversation_id)
        seller_mode = conversation_seller_mode if mode == "customer" else requested_seller_mode

        # Persist seller mode on conversation when seller interacts
        if mode == "seller":
            supabase.table("conversations").update({
                "status": _conversation_status_for_mode(seller_mode),
                "updated_at": datetime.utcnow().isoformat(),
            }).eq("id", conversation_id).execute()

        # Save user message
        save_message(
            conversation_id=conversation_id,
            role="user",
            content=request.message,
        )

        language = _detect_language(request.message)
        objection_type = _classify_objection(request.message)
        purchase_intent = _detect_purchase_intent(request.message)
        forced_agent = "sales_agent" if mode == "customer" else None

        # Route to agent
        result = orchestrator.route(
            user_input=request.message,
            context=request.context,
            store_id=store_id,
            conversation_id=conversation_id,
            forced_agent=forced_agent,
        )

        # Sales enrichment for objection handling and closing actions
        if result.get("agent") == "reporting_agent" and mode != "customer":
            conversational_text, parsed_report = _extract_report_payload(result.get("response", ""))
            result["response"] = conversational_text
            result["output"] = conversational_text
            if parsed_report:
                result["data"] = parsed_report
            result["meta"] = {
                **(result.get("meta") or {}),
                "report_parsed": bool(parsed_report),
            }

        # Sales enrichment for objection handling and closing actions
        if result.get("agent") == "sales_agent":
            discount_allowed = _is_discount_allowed(seller_mode, objection_type)
            response_text = _safe_discount_guardrail(result.get("response", ""), language)
            if objection_type:
                snapshot = _get_store_sales_snapshot(store_id)
                tip = _build_objection_tip(objection_type, language, snapshot, discount_allowed)
                if tip:
                    response_text = f"{response_text}\n\n{tip}"
            if not discount_allowed:
                response_text = _remove_discount_mentions(response_text)
            affirmative_reply = _is_affirmative_reply(request.message)
            heuristic_purchase_ready = purchase_intent or affirmative_reply or _response_confirms_purchase(response_text)
            checkout_signal = None
            if mode == "customer":
                checkout_signal = _llm_checkout_signal(
                    llm_callable=llm,
                    user_message=request.message,
                    assistant_message=response_text,
                    language=language,
                )
            if checkout_signal is not None:
                llm_purchase_ready = bool(checkout_signal.get("purchase_confirmed"))
                llm_confidence = float(checkout_signal.get("confidence", 0.0))
                purchase_ready = heuristic_purchase_ready or (llm_purchase_ready and llm_confidence >= 0.20)
            else:
                purchase_ready = heuristic_purchase_ready

            result["response"] = response_text
            result["output"] = response_text
            sales_actions = _build_sales_actions(language, objection_type) if mode == "seller" and seller_mode == "semi" else []
            if mode == "customer" and purchase_ready:
                checkout_action = {
                    "id": "proceed_checkout",
                    "label": "Pagar ahora" if language == "es" else "Pay now",
                    "type": "checkout",
                }
                sales_actions = [*sales_actions, checkout_action]
            result["meta"] = {
                **(result.get("meta") or {}),
                "objection_type": objection_type,
                "stage": "objection_detected" if objection_type else "normal_sales",
                "actions": sales_actions,
                "purchase_ready": purchase_ready,
                "checkout_signal": checkout_signal,
                "guardrails": {
                    "max_discount_percent": 20,
                    "no_fabrication": True,
                    "language": language,
                },
                "mode": mode,
                "seller_mode": seller_mode,
            }

        requires_approval = mode == "customer" and seller_mode == "semi" and result.get("agent") == "sales_agent"
        if requires_approval:
            draft_id = save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=result.get("response", ""),
                intent=(result.get("meta") or {}).get("objection_type") or result.get("agent"),
                agent="sales_agent_draft",
            )
            result["meta"] = {
                **(result.get("meta") or {}),
                "requires_approval": True,
                "delivery_mode": "draft",
                "draft_id": draft_id,
                "actions": [],
                "purchase_ready": False,
            }
            # Customer only sees ack, not the draft content.
            result["response"] = (
                "Tu solicitud fue recibida. Un vendedor la está revisando para darte la mejor propuesta."
                if language == "es"
                else "Your request was received. A seller is reviewing the best response for you."
            )
            result["output"] = result["response"]
        else:
            # Save assistant response (sent)
            save_message(
                conversation_id=conversation_id,
                role="assistant",
                content=result.get("response", ""),
                intent=(result.get("meta") or {}).get("objection_type") or result.get("agent"),
                agent=result.get("agent"),
            )
            result["meta"] = {
                **(result.get("meta") or {}),
                "requires_approval": False,
                "delivery_mode": "immediate",
            }

        # Include conversation_id in response
        result["conversation_id"] = conversation_id
        return result

    except Exception as e:
        error_msg = f"Error in query_ai: {str(e)}"
        print(error_msg)
        traceback.print_exc()

        return {
            "agent": "error",
            "response": f"An error occurred while processing your request: {str(e)}",
            "error": str(e),
            "publicUrl": None,
            "downloadUrl": None,
            "meta": {
                "planner": "error_handler",
                "summarizer": "error_handler",
                "cached": False,
            },
        }


# ─── Inventory Routes ───────────────────────────────────────────────────────

inventory_router = APIRouter(tags=["Inventory"])


class ProductResponse(BaseModel):
    id: str
    product_id: str
    name: str
    price: Optional[float] = None
    store_id: str
    current_stock: Optional[float] = 0.0
    avg_daily_sales: Optional[float] = 0.0
    safety_stock: Optional[float] = 0.0
    lead_time_days: Optional[int] = 0
    estimated_days_left: Optional[float] = None
    sales_trend: Optional[str] = "stable"
    reorder_qty_suggestion: Optional[int] = 0
    is_critical: bool = False


class StockResponse(BaseModel):
    store_id: str
    products: List[ProductResponse]
    summary: Optional[dict] = None


def _enrich_product(product: dict, store_id: str) -> dict:
    """Calculate derived fields for a product row."""
    current_stock = product.get("current_stock") or 0.0
    avg_daily_sales = product.get("avg_daily_sales") or 0.0
    safety_stock = product.get("safety_stock") or 0.0
    lead_time_days = product.get("lead_time_days") or 0

    estimated_days_left = None
    if avg_daily_sales > 0:
        estimated_days_left = round(current_stock / avg_daily_sales, 1)

    sales_trend = "stable"
    if estimated_days_left is not None:
        if estimated_days_left <= 7:
            sales_trend = "decreasing"
        elif estimated_days_left >= 30:
            sales_trend = "increasing"

    reorder_qty_suggestion = max(0, int(safety_stock + avg_daily_sales * lead_time_days - current_stock))
    is_critical = estimated_days_left is not None and estimated_days_left <= 7

    return {
        "id": str(product.get("id") or ""),
        "product_id": str(product.get("id") or ""),
        "name": str(product.get("name") or ""),
        "price": product.get("price"),
        "store_id": str(product.get("store_id") or store_id),
        "current_stock": float(current_stock),
        "avg_daily_sales": float(avg_daily_sales),
        "safety_stock": float(safety_stock),
        "lead_time_days": int(lead_time_days),
        "estimated_days_left": estimated_days_left,
        "sales_trend": sales_trend,
        "reorder_qty_suggestion": int(reorder_qty_suggestion),
        "is_critical": bool(is_critical),
    }


def _build_summary(products: list[dict]) -> dict:
    total_products = len(products)
    critical_count = sum(1 for p in products if p.get("is_critical"))
    low_stock_count = sum(1 for p in products if p.get("estimated_days_left") and p.get("estimated_days_left") <= 30)
    return {
        "total_products": total_products,
        "critical_count": critical_count,
        "low_stock_count": low_stock_count,
    }


@inventory_router.get("/inventory/stock", response_model=StockResponse)
async def get_stock(store_id: str):
    try:
        result = supabase.table("products").select("*").eq("store_id", store_id).execute()
        products = [_enrich_product(row, store_id) for row in result.data]
        return {"store_id": store_id, "products": products, "summary": _build_summary(products) if products else None}
    except Exception as e:
        print(f"Error in get_stock: {e}")
        traceback.print_exc()
        return {"store_id": store_id, "products": [], "summary": None}


@inventory_router.get("/inventory/items", response_model=StockResponse)
async def get_inventory_items(store_id: str):
    try:
        result = supabase.table("products").select("*").eq("store_id", store_id).execute()
        products = [_enrich_product(row, store_id) for row in result.data]
        return {"store_id": store_id, "products": products, "summary": _build_summary(products)}
    except Exception as e:
        print(f"Error in get_inventory_items: {e}")
        traceback.print_exc()
        return {"store_id": store_id, "products": [], "summary": None}


# ─── Sales Routes ────────────────────────────────────────────────────────────

class SalesProductResponse(BaseModel):
    product_id: str
    product_name: Optional[str] = None
    total_sold: int
    total_revenue: float
    avg_daily_sales: float
    weekly_trend: float = 0.0
    sales_consistency: float = 0.0
    sales_forecast: Optional[dict] = None


class SalesOverviewResponse(BaseModel):
    store_id: str
    products: List[SalesProductResponse]
    summary: Optional[dict] = None


@inventory_router.get("/sales/overview", response_model=SalesOverviewResponse)
async def get_sales_overview(store_id: str):
    try:
        today = datetime.utcnow().date()
        seven_days_ago = (today - timedelta(days=7)).isoformat()
        fourteen_days_ago = (today - timedelta(days=14)).isoformat()

        # Get product names
        products_result = supabase.table("products").select("id, name").eq("store_id", store_id).execute()
        product_names = {p["id"]: p["name"] for p in products_result.data}

        # Last 7 days sales
        current_result = (
            supabase.table("sales_history")
            .select("product_id, quantity, total_amount")
            .eq("store_id", store_id)
            .gte("sale_date", seven_days_ago)
            .execute()
        )

        # Previous 7 days sales (for trend)
        prev_result = (
            supabase.table("sales_history")
            .select("product_id, total_amount")
            .eq("store_id", store_id)
            .gte("sale_date", fourteen_days_ago)
            .lt("sale_date", seven_days_ago)
            .execute()
        )

        # Aggregate current period
        current_by_product = {}
        for s in current_result.data:
            pid = s["product_id"]
            if pid not in current_by_product:
                current_by_product[pid] = {"qty": 0, "revenue": 0}
            current_by_product[pid]["qty"] += s["quantity"]
            current_by_product[pid]["revenue"] += s["total_amount"]

        # Aggregate previous period
        prev_by_product = {}
        for s in prev_result.data:
            pid = s["product_id"]
            prev_by_product[pid] = prev_by_product.get(pid, 0) + s["total_amount"]

        products = []
        total_revenue = 0
        total_avg = 0
        top_product = None

        for pid, agg in sorted(current_by_product.items(), key=lambda x: x[1]["revenue"], reverse=True):
            prev_rev = prev_by_product.get(pid, 0)
            current_rev = agg["revenue"]
            trend = ((current_rev - prev_rev) / prev_rev * 100) if prev_rev > 0 else 0

            product = {
                "product_id": pid,
                "product_name": product_names.get(pid, pid),
                "total_sold": agg["qty"],
                "total_revenue": round(current_rev, 2),
                "avg_daily_sales": round(agg["qty"] / 7, 1),
                "weekly_trend": round(trend, 1),
                "sales_consistency": 0.85,
                "sales_forecast": None,
            }
            products.append(product)
            total_revenue += current_rev
            total_avg += product["avg_daily_sales"]

            if top_product is None or product["total_sold"] > top_product["total_sold"]:
                top_product = product

        summary = {
            "total_revenue": round(total_revenue, 2),
            "avg_daily_sales": round(total_avg, 1),
            "top_product": top_product,
        }

        return {"store_id": store_id, "products": products, "summary": summary}

    except Exception as e:
        print(f"Error in get_sales_overview: {e}")
        traceback.print_exc()
        return {"store_id": store_id, "products": [], "summary": None}


# ─── Store Routes ────────────────────────────────────────────────────────────

class StoreResponse(BaseModel):
    id: str
    name: str
    location: Optional[str] = None


class ObjectionMetricsResponse(BaseModel):
    store_id: str
    total_sales_messages: int
    objections_detected: int
    resolved_estimate: int
    by_type: dict


@inventory_router.get("/stores", response_model=List[StoreResponse])
async def get_stores():
    try:
        result = supabase.table("stores").select("*").execute()
        stores = []
        for store in result.data:
            stores.append({
                "id": str(store.get("id") or ""),
                "name": str(store.get("name") or ""),
                "location": store.get("location"),
            })
        print(f"get_stores: Found {len(stores)} stores")
        return stores
    except Exception as e:
        print(f"get_stores error: {e}")
        traceback.print_exc()
        return []


@inventory_router.get("/sales/objections/metrics", response_model=ObjectionMetricsResponse)
async def get_objection_metrics(store_id: str):
    try:
        conversations_result = supabase.table("conversations").select("id").eq("store_id", store_id).execute()
        conversation_ids = [row["id"] for row in (conversations_result.data or [])]

        if not conversation_ids:
            return {
                "store_id": store_id,
                "total_sales_messages": 0,
                "objections_detected": 0,
                "resolved_estimate": 0,
                "by_type": {"price": 0, "timing": 0, "trust": 0, "competition": 0},
            }

        messages_result = (
            supabase.table("messages")
            .select("content,intent,agent,created_at")
            .in_("conversation_id", conversation_ids)
            .eq("role", "assistant")
            .eq("agent", "sales_agent")
            .execute()
        )
        messages = messages_result.data or []

        by_type = {"price": 0, "timing": 0, "trust": 0, "competition": 0}
        resolved_estimate = 0
        for message in messages:
            intent = message.get("intent")
            if intent in by_type:
                by_type[intent] += 1

            content = (message.get("content") or "").lower()
            if "reserve" in content or "reserva" in content or "would you like to proceed" in content or "quieres que lo reserve" in content:
                resolved_estimate += 1

        objections_detected = sum(by_type.values())
        return {
            "store_id": store_id,
            "total_sales_messages": len(messages),
            "objections_detected": objections_detected,
            "resolved_estimate": resolved_estimate,
            "by_type": by_type,
        }
    except Exception as e:
        print(f"get_objection_metrics error: {e}")
        traceback.print_exc()
        return {
            "store_id": store_id,
            "total_sales_messages": 0,
            "objections_detected": 0,
            "resolved_estimate": 0,
            "by_type": {"price": 0, "timing": 0, "trust": 0, "competition": 0},
        }


class ConversationModeRequest(BaseModel):
    conversation_id: str
    seller_mode: str


class DraftSendRequest(BaseModel):
    conversation_id: str
    reply_text: str
    draft_id: str | None = None


class CheckoutSimulateRequest(BaseModel):
    conversation_id: str
    store_id: str | None = None
    customer_name: str
    email: str
    address: str
    payment_method: str


@router.post("/conversation/mode")
async def set_conversation_mode(request: ConversationModeRequest):
    try:
        seller_mode = _normalize_seller_mode(request.seller_mode)
        now = datetime.utcnow().isoformat()
        supabase.table("conversations").update({
            "status": _conversation_status_for_mode(seller_mode),
            "updated_at": now,
        }).eq("id", request.conversation_id).execute()
        return {"conversation_id": request.conversation_id, "seller_mode": seller_mode}
    except Exception as e:
        print(f"set_conversation_mode error: {e}")
        traceback.print_exc()
        return {"conversation_id": request.conversation_id, "seller_mode": "semi"}


@router.get("/conversation/mode")
async def get_conversation_mode(conversation_id: str):
    try:
        seller_mode = _get_seller_mode_from_conversation(conversation_id)
        return {"conversation_id": conversation_id, "seller_mode": seller_mode}
    except Exception as e:
        print(f"get_conversation_mode error: {e}")
        traceback.print_exc()
        return {"conversation_id": conversation_id, "seller_mode": "semi"}


@router.post("/seller/send-draft")
async def send_seller_draft(request: DraftSendRequest):
    try:
        # Persist final assistant message visible to both sides.
        save_message(
            conversation_id=request.conversation_id,
            role="assistant",
            content=request.reply_text,
            intent="approved_reply",
            agent="sales_agent",
        )

        # Optionally delete consumed draft.
        if request.draft_id:
            supabase.table("messages").delete().eq("id", request.draft_id).execute()

        return {"ok": True}
    except Exception as e:
        print(f"send_seller_draft error: {e}")
        traceback.print_exc()
        return {"ok": False}


@router.post("/checkout/simulate")
async def simulate_checkout(request: CheckoutSimulateRequest):
    try:
        payment_method = (request.payment_method or "").lower().strip()
        if payment_method not in PAYMENT_METHODS:
            return {"ok": False, "error": "invalid_payment_method"}

        now = datetime.utcnow().isoformat()
        payment_id = f"sim-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}"
        payment_url = f"https://demo-pay.cruisely.local/pay/{payment_id}"
        language = _detect_language(request.address + " " + request.customer_name)

        summary = (
            f"Checkout simulated | name={request.customer_name} | email={request.email} | "
            f"payment_method={payment_method} | address={request.address} | at={now}"
        )
        save_message(
            conversation_id=request.conversation_id,
            role="assistant",
            content=summary,
            intent="checkout_simulated",
            agent="checkout_agent",
        )

        email_sent, email_error = _send_checkout_email(
            to_email=request.email,
            customer_name=request.customer_name,
            payment_url=payment_url,
            language=language,
        )

        return {
            "ok": True,
            "payment_id": payment_id,
            "payment_url": payment_url,
            "email_sent": email_sent,
            "email_error": email_error,
        }
    except Exception as e:
        print(f"simulate_checkout error: {e}")
        traceback.print_exc()
        return {"ok": False, "error": str(e)}


@router.get("/conversation/messages", response_model=List[ConversationMessageResponse])
async def get_conversation_messages(conversation_id: str, limit: int = 30, viewer_mode: str = "seller"):
    try:
        safe_limit = max(1, min(limit, 100))
        query = (
            supabase.table("messages")
            .select("id, role, content, intent, agent, created_at")
            .eq("conversation_id", conversation_id)
            .order("created_at", desc=False)
        )
        result = query.limit(safe_limit).execute()
        messages = result.data or []
        if (viewer_mode or "seller").lower() == "customer":
            messages = [m for m in messages if not str(m.get("agent") or "").endswith("_draft")]
        return messages
    except Exception as e:
        print(f"get_conversation_messages error: {e}")
        traceback.print_exc()
        return []
