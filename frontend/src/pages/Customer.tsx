import { ChatBot } from "@/components/dashboard/ChatBot";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useEffect, useMemo, useState } from "react";
import { useSearchParams } from "react-router-dom";
import { getConversationMode } from "@/services/api";

const Customer = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const sharedConversationId = searchParams.get("conv");
  const [sellerMode, setSellerMode] = useState<"auto" | "semi">("semi");
  const sellerUrl = useMemo(() => {
    if (!sharedConversationId) return `${window.location.origin}/`;
    return `${window.location.origin}/?conv=${encodeURIComponent(sharedConversationId)}`;
  }, [sharedConversationId]);

  const handleConversationIdChange = (conversationId: string) => {
    const next = new URLSearchParams(searchParams);
    next.set("conv", conversationId);
    setSearchParams(next, { replace: true });
  };

  useEffect(() => {
    if (!sharedConversationId) {
      setSellerMode("semi");
      return;
    }
    getConversationMode(sharedConversationId)
      .then((data) => setSellerMode(data.seller_mode || "semi"))
      .catch(() => setSellerMode("semi"));
  }, [sharedConversationId]);

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/30">
      <main className="p-6 max-w-5xl mx-auto space-y-4">
        <Card className="shadow-soft">
          <CardHeader className="border-b">
            <div className="flex items-center justify-between gap-3">
              <CardTitle className="text-xl">Customer Chat</CardTitle>
              <Button size="sm" variant="outline" asChild>
                <a href={sellerUrl} target="_blank" rel="noreferrer">
                  Go to seller dashboard
                </a>
              </Button>
            </div>
          </CardHeader>
          <CardContent className="p-4">
            <ChatBot
              mode="customer"
              sellerMode={sellerMode}
              embedded
              defaultOpen
              sharedConversationId={sharedConversationId}
              onConversationIdChange={handleConversationIdChange}
              enableRealtimeSync={Boolean(sharedConversationId)}
            />
          </CardContent>
        </Card>
      </main>
    </div>
  );
};

export default Customer;
