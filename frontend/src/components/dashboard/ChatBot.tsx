import { useState, useRef, useEffect, useMemo, useCallback } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Label } from "@/components/ui/label";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Badge } from "@/components/ui/badge";
import { Dialog, DialogContent, DialogDescription, DialogFooter, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { useStore } from "@/context/StoreContext";
import { ChatMessage, ChatIntent } from "@/types/inventory";
import { getConversationMessages, normalizeIntent, orchestrate, sendSellerDraft, simulateCheckout } from "@/services/api";
import { MessageSquare, Send, Bot, User } from "lucide-react";
import { cn } from "@/lib/utils";

interface ChatBotProps {
  onStockData?: (data: ChatMessage["data"]) => void;
  onSalesData?: (data: ChatMessage["data"]) => void;
  onReportData?: (data: ChatMessage["data"]) => void;
  onReportShortcut?: () => void;
  mode?: "seller" | "customer";
  embedded?: boolean;
  defaultOpen?: boolean;
  sharedConversationId?: string | null;
  onConversationIdChange?: (conversationId: string) => void;
  enableRealtimeSync?: boolean;
  pollingMs?: number;
  sellerMode?: "auto" | "semi";
}

const intentIcons: Record<ChatIntent, typeof Bot> = {
  stock: Bot,
  sales: Bot,
  report: Bot,
  general: Bot,
};

const intentColors: Record<ChatIntent, string> = {
  stock: "bg-warning/10 text-warning border-warning/20",
  sales: "bg-success/10 text-success border-success/20",
  report: "bg-primary/10 text-primary border-primary/20",
  general: "bg-muted text-muted-foreground border-border",
};

export function ChatBot({
  onStockData,
  onSalesData,
  onReportData,
  onReportShortcut,
  mode = "seller",
  embedded = false,
  defaultOpen = false,
  sharedConversationId,
  onConversationIdChange,
  enableRealtimeSync = false,
  pollingMs = 2500,
  sellerMode = "semi",
}: ChatBotProps) {
  const [storeMessages, setStoreMessages] = useState<Record<string, ChatMessage[]>>({});
  const [storeConversationIds, setStoreConversationIds] = useState<Record<string, string>>({});
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isOpen, setIsOpen] = useState(defaultOpen || embedded);
  const { currentStoreId } = useStore();
  const scrollRef = useRef<HTMLDivElement>(null);
  const activeStoreId = currentStoreId ?? "";
  const effectiveConversationId = sharedConversationId || storeConversationIds[activeStoreId];
  const messageScopeKey = `${activeStoreId}:${mode}:${sharedConversationId || "local"}`;
  const sellerMonitoringMode = mode === "seller" && enableRealtimeSync && Boolean(sharedConversationId);
  const [draftId, setDraftId] = useState<string | null>(null);
  const [draftReply, setDraftReply] = useState("");
  const [isSendingDraft, setIsSendingDraft] = useState(false);
  const [isCheckoutOpen, setIsCheckoutOpen] = useState(false);
  const [isCheckoutSubmitting, setIsCheckoutSubmitting] = useState(false);
  const [checkoutName, setCheckoutName] = useState("");
  const [checkoutEmail, setCheckoutEmail] = useState("");
  const [checkoutAddress, setCheckoutAddress] = useState("");
  const [checkoutMethod, setCheckoutMethod] = useState<"credit_card" | "debit_card" | "bank_transfer" | "cash_on_delivery">("credit_card");

  const messages = useMemo(() => storeMessages[messageScopeKey] || [], [storeMessages, messageScopeKey]);

  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [messages]);

  const mapSyncedMessages = useCallback((rows: Awaited<ReturnType<typeof getConversationMessages>>): ChatMessage[] => {
    const responseConfirmsPurchase = (text: string) => {
      const value = (text || "").toLowerCase();
      const markers = [
        "would you like to proceed",
        "ready to proceed",
        "confirm your purchase",
        "proceed to payment",
        "quieres proceder",
        "listo para proceder",
        "confirmar tu compra",
        "pasar al pago",
      ];
      return markers.some((m) => value.includes(m));
    };

    return rows.map((row, index) => {
      const isObjection =
        row.intent === "price" ||
        row.intent === "timing" ||
        row.intent === "trust" ||
        row.intent === "competition";

      const isUser =
        mode === "seller" && enableRealtimeSync
          ? row.role === "assistant"
          : row.role === "user";
      const normalizedIntent =
        row.role === "assistant" ? normalizeIntent(row.agent || "general") : undefined;
      const checkoutAction =
        mode === "customer" && row.role === "assistant" && responseConfirmsPurchase(row.content || "")
          ? [{ id: "proceed_checkout", label: "Proceed to payment", type: "checkout" as const }]
          : [];
      return {
        id: row.id || `synced-${row.created_at || index}`,
        type: isUser ? "user" : "bot",
        content: row.content || "",
        intent: isUser ? undefined : normalizedIntent,
        timestamp: row.created_at ? new Date(row.created_at) : new Date(),
        meta: {
          ...(isObjection
            ? {
              objection_type: row.intent as "price" | "timing" | "trust" | "competition",
            }
            : {}),
          ...(String(row.agent || "").endsWith("_draft")
            ? {
                requires_approval: true,
                delivery_mode: "draft",
                draft_id: row.id,
              }
            : {}),
          ...(checkoutAction.length
            ? {
                actions: checkoutAction,
              }
            : {}),
        },
      };
    });
  }, [mode, enableRealtimeSync]);

  useEffect(() => {
    if (!enableRealtimeSync || !effectiveConversationId || !activeStoreId) return;

    let isMounted = true;
    const syncOnce = async () => {
      try {
        const rows = await getConversationMessages(effectiveConversationId, 60, mode);
        if (!isMounted) return;
        const latestDraft = rows
          .slice()
          .reverse()
          .find((row) => String(row.agent || "").endsWith("_draft"));
        if (sellerMonitoringMode && sellerMode === "semi") {
          if (latestDraft && latestDraft.id !== draftId) {
            setDraftId(latestDraft.id);
            setDraftReply(latestDraft.content || "");
          }
          if (!latestDraft) {
            setDraftId(null);
            setDraftReply("");
          }
        }
        setStoreMessages((prev) => ({
          ...prev,
          [messageScopeKey]: mapSyncedMessages(rows),
        }));
      } catch (error) {
        console.error("Conversation sync failed:", error);
      }
    };

    void syncOnce();
    const timer = setInterval(syncOnce, pollingMs);
    return () => {
      isMounted = false;
      clearInterval(timer);
    };
  }, [enableRealtimeSync, effectiveConversationId, activeStoreId, pollingMs, mapSyncedMessages, sellerMonitoringMode, sellerMode, draftId, mode, messageScopeKey]);

  const handleConfirmDraftSend = async () => {
    if (!effectiveConversationId || !draftReply.trim() || !draftId) return;
    try {
      setIsSendingDraft(true);
      await sendSellerDraft(effectiveConversationId, draftReply.trim(), draftId);
      setDraftId(null);
      setDraftReply("");
    } catch (error) {
      console.error("Failed to send seller draft:", error);
    } finally {
      setIsSendingDraft(false);
    }
  };

  const handleActionClick = (action: { id: string; label: string; type: string }) => {
    if (action.type === "checkout") {
      setIsCheckoutOpen(true);
      return;
    }

    const label = action.label;
    const isSpanish = /aplicar|reservar|alternativas|descuento/i.test(label);
    const confirmation: ChatMessage = {
      id: `action-${Date.now()}`,
      type: "bot",
      content: isSpanish
        ? `Acción ejecutada: ${label}. Continúa la conversación para afinar la oferta.`
        : `Action executed: ${label}. You can continue the conversation to refine the offer.`,
      intent: "sales",
      timestamp: new Date(),
    };
    setStoreMessages((prev) => ({
      ...prev,
      [messageScopeKey]: [...(prev[messageScopeKey] || []), confirmation],
    }));
  };

  const handleSend = async () => {
    if (sellerMonitoringMode) return;

    if (!currentStoreId) {
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        type: "bot",
        content: "Select a store first to start chatting with the assistant.",
        intent: "general",
        timestamp: new Date(),
      };
      setStoreMessages(prev => ({
        ...prev,
        [messageScopeKey]: [...(prev[messageScopeKey] || []), errorMessage],
      }));
      return;
    }

    if (!input.trim() || isLoading) return;

    const userMessage: ChatMessage = {
      id: `user-${Date.now()}`,
      type: "user",
      content: input.trim(),
      timestamp: new Date(),
    };

    setStoreMessages(prev => ({
      ...prev,
      [messageScopeKey]: [...(prev[messageScopeKey] || []), userMessage],
    }));
    setInput("");
    setIsLoading(true);

    try {
      const conversationId = effectiveConversationId;
      const response = await orchestrate(input, currentStoreId, conversationId, mode, sellerMode);
      const { agent, output = response.response, data, publicUrl } = response;

      // Track conversation_id from backend
      if (response.conversation_id) {
        onConversationIdChange?.(response.conversation_id);
        setStoreConversationIds(prev => ({
          ...prev,
          [activeStoreId]: response.conversation_id!,
        }));
      }

      const botMessage: ChatMessage = {
        id: `bot-${Date.now()}`,
        type: "bot",
        content: output,
        intent: agent ? normalizeIntent(agent) : "general",
        data,
        publicUrl,
        downloadUrl: publicUrl,
        timestamp: new Date(),
        meta: response.meta || { cached: false },
      };

      setStoreMessages(prev => ({
        ...prev,
        [messageScopeKey]: [...(prev[messageScopeKey] || []), botMessage],
      }));

      if (mode === "seller") {
        if (agent === "stock_agent") onStockData?.(data);
        if (agent === "sales_agent") onSalesData?.(data);
        if (agent === "reporting_agent") onReportData?.(data);
      }
    } catch (error) {
      const errorMessage: ChatMessage = {
        id: `error-${Date.now()}`,
        type: "bot",
        content: error instanceof Error ? `Error: ${error.message}` : "An error occurred. Please try again.",
        intent: "general",
        timestamp: new Date(),
      };
      setStoreMessages(prev => ({
        ...prev,
        [messageScopeKey]: [...(prev[messageScopeKey] || []), errorMessage],
      }));
      console.error("Orchestrate error:", error);
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <>
      {!embedded && (
        <Button
          onClick={() => setIsOpen(true)}
          className={cn(
            "fixed bottom-6 right-6 h-14 w-14 rounded-full shadow-floating z-50 transition-all duration-200",
            "bg-primary hover:bg-primary/90",
            isOpen && "scale-0 opacity-0"
          )}
        >
          <MessageSquare className="h-6 w-6" />
        </Button>
      )}

      <div
        className={cn(
          embedded
            ? "w-full h-[70vh] max-h-[760px]"
            : "fixed bottom-6 right-6 w-96 h-[32rem] z-50 transition-all duration-300 origin-bottom-right",
          isOpen || embedded ? "scale-100 opacity-100" : "scale-0 opacity-0 pointer-events-none"
        )}
      >
        <Card className="h-full flex flex-col shadow-floating border-border">
          <CardHeader className="pb-3 flex-shrink-0 border-b bg-card rounded-t-lg">
            <div className="flex items-center justify-between">
              <CardTitle className="flex items-center gap-2 text-base font-semibold">
                <div className="p-1.5 rounded-lg bg-primary/10">
                  <Bot className="h-4 w-4 text-primary" />
                </div>
                AI Assistant
              </CardTitle>
              {!embedded && (
                <Button variant="ghost" size="icon" className="h-8 w-8" onClick={() => setIsOpen(false)}>
                  X
                </Button>
              )}
            </div>
          </CardHeader>

          <ScrollArea className="flex-1 p-4" ref={scrollRef}>
            <div className="space-y-4">
              {messages.map((message) => (
                <div
                  key={message.id}
                  className={cn(
                    "flex gap-3 animate-slide-up",
                    message.type === "user" && "flex-row-reverse"
                  )}
                >
                  <div
                    className={cn(
                      "h-8 w-8 rounded-full flex items-center justify-center flex-shrink-0",
                      message.type === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                    )}
                  >
                    {message.type === "user" ? <User className="h-4 w-4" /> : <Bot className="h-4 w-4" />}
                  </div>
                  <div className={cn("flex flex-col gap-2 max-w-[80%]", message.type === "user" && "items-end")}>
                    <div
                      className={cn(
                        "rounded-lg px-3 py-2 text-sm",
                        message.type === "user" ? "bg-primary text-primary-foreground" : "bg-muted"
                      )}
                    >
                      {message.content}
                    </div>
                    {mode === "seller" && message.intent && message.type === "bot" && (
                      <div className="flex items-center gap-2 flex-wrap">
                        <button
                          type="button"
                          onClick={() => {
                            if (message.intent === "report") onReportShortcut?.();
                          }}
                          className={cn("rounded-full", message.intent === "report" && "cursor-pointer")}
                          title={message.intent === "report" ? "Open report panel" : undefined}
                        >
                          <Badge variant="outline" className={cn("text-xs w-fit", intentColors[message.intent])}>
                            {(() => {
                              const Icon = intentIcons[message.intent];
                              return <Icon className="h-3 w-3 mr-1" />;
                            })()}
                            {message.intent}
                          </Badge>
                        </button>
                        {mode === "seller" && message.meta?.objection_type && (
                          <Badge variant="outline" className="text-xs w-fit border-warning/30 text-warning">
                            objection: {message.meta.objection_type}
                          </Badge>
                        )}
                      </div>
                    )}
                    {message.type === "bot" && message.meta?.actions && message.meta.actions.length > 0 && (
                      <div className="flex gap-2 flex-wrap">
                        {message.meta.actions.map((action) => (
                          <Button
                            key={`${message.id}-${action.id}`}
                            size="sm"
                            variant="outline"
                            className="h-7 text-xs"
                            onClick={() => handleActionClick(action)}
                          >
                            {action.label}
                          </Button>
                        ))}
                      </div>
                    )}
                    {message.publicUrl && (
                      <div className="flex gap-2">
                        <Button size="sm" variant="outline" className="h-7 text-xs">
                          Open
                        </Button>
                        <Button size="sm" variant="outline" className="h-7 text-xs">
                          Download
                        </Button>
                      </div>
                    )}
                  </div>
                </div>
              ))}
              {isLoading && (
                <div className="flex gap-3 animate-slide-up">
                  <div className="h-8 w-8 rounded-full bg-muted flex items-center justify-center">
                    <Bot className="h-4 w-4" />
                  </div>
                  <div className="bg-muted rounded-lg px-4 py-3">
                    <div className="flex gap-1">
                      <div className="w-2 h-2 rounded-full bg-foreground/30 animate-pulse-soft" />
                      <div className="w-2 h-2 rounded-full bg-foreground/30 animate-pulse-soft" style={{ animationDelay: "0.2s" }} />
                      <div className="w-2 h-2 rounded-full bg-foreground/30 animate-pulse-soft" style={{ animationDelay: "0.4s" }} />
                    </div>
                  </div>
                </div>
              )}
            </div>
          </ScrollArea>

          <CardContent className="p-3 border-t flex-shrink-0">
            {sellerMonitoringMode && sellerMode === "semi" && draftId && (
              <div className="mb-3 rounded-md border p-2 bg-muted/30">
                <p className="text-xs font-medium mb-2">Draft reply pending approval</p>
                <Textarea
                  value={draftReply}
                  onChange={(e) => setDraftReply(e.target.value)}
                  className="min-h-[90px] text-sm"
                />
                <div className="mt-2 flex justify-end gap-2">
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    onClick={() => setInput(draftReply)}
                  >
                    Copy to input
                  </Button>
                  <Button
                    type="button"
                    size="sm"
                    onClick={handleConfirmDraftSend}
                    disabled={isSendingDraft || !draftReply.trim()}
                  >
                    {isSendingDraft ? "Sending..." : "Confirm & send"}
                  </Button>
                </div>
              </div>
            )}
            <form
              onSubmit={(e) => {
                e.preventDefault();
                handleSend();
              }}
              className="flex gap-2"
            >
              <Input
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={
                  sellerMonitoringMode
                    ? "Monitoring shared customer conversation (read-only)"
                    : currentStoreId
                      ? mode === "customer"
                        ? "Ask about products, prices, or availability..."
                        : "Ask about inventory, sales, or reports..."
                      : "Select a store to enable chat"
                }
                className="flex-1 text-sm"
                disabled={isLoading || !currentStoreId || sellerMonitoringMode}
              />
              <Button type="submit" size="icon" disabled={!currentStoreId || !input.trim() || isLoading || sellerMonitoringMode}>
                <Send className="h-4 w-4" />
              </Button>
            </form>
          </CardContent>
        </Card>
      </div>
      <Dialog open={isCheckoutOpen} onOpenChange={setIsCheckoutOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Complete payment</DialogTitle>
            <DialogDescription>
              Simulated checkout for demo purposes. No real charge is made.
            </DialogDescription>
          </DialogHeader>

          <div className="grid gap-3">
            <div className="grid gap-1.5">
              <Label htmlFor="checkout-name">Full name</Label>
              <Input id="checkout-name" value={checkoutName} onChange={(e) => setCheckoutName(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="checkout-email">Email</Label>
              <Input id="checkout-email" type="email" value={checkoutEmail} onChange={(e) => setCheckoutEmail(e.target.value)} />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="checkout-address">Address</Label>
              <Textarea id="checkout-address" value={checkoutAddress} onChange={(e) => setCheckoutAddress(e.target.value)} className="min-h-[72px]" />
            </div>
            <div className="grid gap-1.5">
              <Label htmlFor="checkout-method">Payment method</Label>
              <select
                id="checkout-method"
                value={checkoutMethod}
                onChange={(e) => setCheckoutMethod(e.target.value as typeof checkoutMethod)}
                className="h-10 rounded-md border border-input bg-background px-3 text-sm"
              >
                <option value="credit_card">Credit card</option>
                <option value="debit_card">Debit card</option>
                <option value="bank_transfer">Bank transfer</option>
                <option value="cash_on_delivery">Cash on delivery</option>
              </select>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => setIsCheckoutOpen(false)} disabled={isCheckoutSubmitting}>
              Cancel
            </Button>
            <Button
              type="button"
              disabled={isCheckoutSubmitting || !checkoutName.trim() || !checkoutEmail.trim() || !checkoutAddress.trim() || !effectiveConversationId}
              onClick={async () => {
                if (!effectiveConversationId) return;
                try {
                  setIsCheckoutSubmitting(true);
                  const result = await simulateCheckout({
                    conversation_id: effectiveConversationId,
                    store_id: currentStoreId || undefined,
                    customer_name: checkoutName.trim(),
                    email: checkoutEmail.trim(),
                    address: checkoutAddress.trim(),
                    payment_method: checkoutMethod,
                  });

                  const success = result.ok;
                  const confirmation: ChatMessage = {
                    id: `checkout-${Date.now()}`,
                    type: "bot",
                    content: success
                      ? `Simulated purchase confirmed. ${result.email_sent ? "Email sent successfully." : "SMTP not configured or email failed; purchase still recorded."}`
                      : `Checkout failed: ${result.error || "unknown_error"}`,
                    intent: "sales",
                    timestamp: new Date(),
                  };
                  setStoreMessages((prev) => ({
                    ...prev,
                    [messageScopeKey]: [...(prev[messageScopeKey] || []), confirmation],
                  }));
                  if (success) {
                    setIsCheckoutOpen(false);
                    setCheckoutName("");
                    setCheckoutEmail("");
                    setCheckoutAddress("");
                    setCheckoutMethod("credit_card");
                  }
                } catch (error) {
                  const confirmation: ChatMessage = {
                    id: `checkout-${Date.now()}`,
                    type: "bot",
                    content: error instanceof Error ? `Checkout failed: ${error.message}` : "Checkout failed",
                    intent: "sales",
                    timestamp: new Date(),
                  };
                  setStoreMessages((prev) => ({
                    ...prev,
                    [messageScopeKey]: [...(prev[messageScopeKey] || []), confirmation],
                  }));
                } finally {
                  setIsCheckoutSubmitting(false);
                }
              }}
            >
              {isCheckoutSubmitting ? "Processing..." : "Simulate payment"}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
