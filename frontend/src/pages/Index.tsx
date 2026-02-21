import { useState, useEffect, useRef } from "react";
import { DashboardHeader } from "@/components/dashboard/DashboardHeader";
import { KPICard } from "@/components/dashboard/KPICard";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StockTable } from "@/components/dashboard/StockTable";
import { SalesOverview } from "@/components/dashboard/SalesOverview";
import { ReportViewer } from "@/components/dashboard/ReportViewer";
import { ChatBot } from "@/components/dashboard/ChatBot";
import { useStore } from "@/context/StoreContext";
import type { StockResponse, SalesResponse, ReportData, ObjectionMetrics, ChatMessage } from "@/types/inventory";
import { Package, AlertTriangle, TrendingUp, Boxes, MessageCircleWarning, Bot, UserCheck } from "lucide-react";
import { getConversationMode, getInventoryItems, getSalesOverview, getObjectionMetrics, setConversationMode } from "@/services/api";
import { useSearchParams } from "react-router-dom";

const Index = () => {
  const [searchParams, setSearchParams] = useSearchParams();
  const { currentStoreId } = useStore();
  const [stockData, setStockData] = useState<StockResponse | null>(null);
  const [salesData, setSalesData] = useState<SalesResponse | null>(null);
  const [objectionMetrics, setObjectionMetrics] = useState<ObjectionMetrics | null>(null);
  const [reports, setReports] = useState<ReportData[]>([]);
  const [loading, setLoading] = useState(true);
  const reportSectionRef = useRef<HTMLElement | null>(null);
  const sharedConversationId = searchParams.get("conv");
  const [sellerMode, setSellerMode] = useState<"auto" | "semi">("semi");


  useEffect(() => {
    if (!currentStoreId) return;
    setLoading(true);

    getInventoryItems(currentStoreId)
      .then((data: StockResponse) => {
        setStockData(data);
        setLoading(false);
      })
      .catch((err) => {
        console.error(err);
        setLoading(false);
      });
  }, [currentStoreId]);


  useEffect(() => {
    if (!currentStoreId) return;

    getSalesOverview(currentStoreId)
      .then((data: SalesResponse) => {
        setSalesData(data);
      })
      .catch(console.error);
  }, [currentStoreId]);

  useEffect(() => {
    if (!currentStoreId) return;
    getObjectionMetrics(currentStoreId)
      .then((data) => setObjectionMetrics(data))
      .catch((err) => console.error("Failed to load objection metrics", err));
  }, [currentStoreId]);

  useEffect(() => {
    if (!sharedConversationId) return;
    getConversationMode(sharedConversationId)
      .then((data) => setSellerMode(data.seller_mode || "semi"))
      .catch(() => setSellerMode("semi"));
  }, [sharedConversationId]);

  
  const handleReportData = (data: ChatMessage["data"]) => {
    if (!data || Array.isArray(data)) return;

    const payload = data as Record<string, unknown>;
    const summary = typeof payload.summary === "string" ? payload.summary : undefined;
    const kpis = payload.kpis && typeof payload.kpis === "object" ? (payload.kpis as Record<string, unknown>) : undefined;
    const table = Array.isArray(payload.table) ? (payload.table as Array<Record<string, unknown>>) : undefined;
    const publicUrl = typeof payload.publicUrl === "string" ? payload.publicUrl : undefined;
    const downloadUrl = typeof payload.downloadUrl === "string" ? payload.downloadUrl : undefined;

    if (!summary && !kpis && !table && !publicUrl) return;

    setReports((prev) => [
      {
        title: "AI Generated Report",
        type: "inventory",
        publicUrl,
        downloadUrl,
        generatedAt: new Date().toISOString(),
        summary,
        kpis,
        table,
      },
      ...prev,
    ]);
  };

  const handleReportShortcut = () => {
    reportSectionRef.current?.scrollIntoView({ behavior: "smooth", block: "start" });
  };

  const handleConversationIdChange = (conversationId: string) => {
    if (!sharedConversationId) return;
    const next = new URLSearchParams(searchParams);
    next.set("conv", conversationId);
    setSearchParams(next, { replace: true });
  };

  const handleSellerModeChange = async (nextMode: "auto" | "semi") => {
    setSellerMode(nextMode);
    if (sharedConversationId) {
      try {
        await setConversationMode(sharedConversationId, nextMode);
      } catch (error) {
        console.error("Failed to set conversation mode", error);
      }
    }
  };

  const criticalCount = stockData?.products.filter((p) => p.is_critical).length || 0;
  const totalProducts = stockData?.products.length || 0;
  const lowStockCount =
    stockData?.products.filter(
      (p) => p.estimated_days_left && p.estimated_days_left <= 30
    ).length || 0;
  const objectionTotal = objectionMetrics?.objections_detected || 0;
  const objectionDistribution = [
    { key: "price", label: "Price", value: objectionMetrics?.by_type.price || 0 },
    { key: "timing", label: "Timing", value: objectionMetrics?.by_type.timing || 0 },
    { key: "trust", label: "Trust", value: objectionMetrics?.by_type.trust || 0 },
    { key: "competition", label: "Competition", value: objectionMetrics?.by_type.competition || 0 },
  ];

  return (
    <div className="min-h-screen bg-gradient-to-b from-background to-muted/30">
      <DashboardHeader />

      <main className="p-6 max-w-7xl mx-auto space-y-6">
        <section>
          <Card className="shadow-soft border-primary/15">
            <CardContent className="p-4 md:p-5">
              <div className="flex flex-col gap-4 md:flex-row md:items-center md:justify-between">
                <div>
                  <p className="text-xs uppercase tracking-wide text-muted-foreground">Conversation Control</p>
                  <h3 className="text-base font-semibold">Seller Assistant Mode</h3>
                  <p className="text-sm text-muted-foreground mt-1">
                    {sellerMode === "auto"
                      ? "Fully automatic replies focused on persuasion, without discounts."
                      : "Semi-automatic flow with draft approval before sending replies."}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Button
                    type="button"
                    variant={sellerMode === "auto" ? "default" : "outline"}
                    size="sm"
                    onClick={() => handleSellerModeChange("auto")}
                    className="gap-2"
                  >
                    <Bot className="h-4 w-4" />
                    Auto
                  </Button>
                  <Button
                    type="button"
                    variant={sellerMode === "semi" ? "default" : "outline"}
                    size="sm"
                    onClick={() => handleSellerModeChange("semi")}
                    className="gap-2"
                  >
                    <UserCheck className="h-4 w-4" />
                    Semi
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </section>

        {/* KPI Cards */}
        <section className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-5 gap-4">
          <KPICard
            title="Total Products"
            value={totalProducts}
            icon={Boxes}
            variant="default"
          />
          <KPICard
            title="Critical Stock"
            value={criticalCount}
            subtitle="Needs immediate action"
            icon={AlertTriangle}
            variant="destructive"
          />
          <KPICard
            title="Low Stock Items"
            value={lowStockCount}
            subtitle="Under 30 days supply"
            icon={Package}
            variant="warning"
          />
          <KPICard
            title="Total Revenue"
            value={`$${((salesData?.summary?.total_revenue || 0) / 1000).toFixed(1)}K`}
            icon={TrendingUp}
            trend={{ value: 12.5, label: "vs last period" }}
            variant="success"
          />
          <KPICard
            title="Objections Detected"
            value={objectionMetrics?.objections_detected || 0}
            subtitle={`${objectionMetrics?.resolved_estimate || 0} estimated resolved`}
            icon={MessageCircleWarning}
            variant="warning"
          />
        </section>

        {/* Main Content Grid */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Stock Table - Takes 2 columns */}
          <div className="lg:col-span-2">
            <StockTable products={stockData?.products || []} loading={loading} />
          </div>

          {/* Objection Panel */}
          <div className="lg:col-span-1">
            <Card className="shadow-soft">
              <CardHeader className="pb-3">
                <CardTitle className="text-lg font-semibold">Objection Metrics</CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                <div className="grid grid-cols-2 gap-3">
                  <div className="rounded-lg border bg-muted/20 p-3">
                    <p className="text-xs text-muted-foreground">Detected</p>
                    <p className="text-2xl font-semibold">{objectionTotal}</p>
                  </div>
                  <div className="rounded-lg border bg-muted/20 p-3">
                    <p className="text-xs text-muted-foreground">Estimated Resolved</p>
                    <p className="text-2xl font-semibold">{objectionMetrics?.resolved_estimate || 0}</p>
                  </div>
                </div>
                <div className="space-y-3">
                  {objectionDistribution.map((item) => {
                    const pct = objectionTotal > 0 ? Math.round((item.value / objectionTotal) * 100) : 0;
                    return (
                      <div key={item.key} className="space-y-1.5">
                        <div className="flex items-center justify-between text-xs">
                          <span className="font-medium">{item.label}</span>
                          <span className="text-muted-foreground">{item.value} ({pct}%)</span>
                        </div>
                        <div className="h-2 rounded-full bg-muted">
                          <div className="h-2 rounded-full bg-primary transition-all" style={{ width: `${pct}%` }} />
                        </div>
                      </div>
                    );
                  })}
                </div>
              </CardContent>
            </Card>
          </div>
        </div>

        {/* Sales Overview */}
        <section>
          <SalesOverview data={salesData} loading={loading} />
        </section>

        <section ref={reportSectionRef}>
          <ReportViewer reports={reports} loading={false} />
        </section>
      </main>

      {/* Floating ChatBot */}
      <ChatBot
        onStockData={() => {}}
        onSalesData={() => {}}
        onReportData={handleReportData}
        onReportShortcut={handleReportShortcut}
        mode="seller"
        sellerMode={sellerMode}
        sharedConversationId={sharedConversationId}
        onConversationIdChange={handleConversationIdChange}
        enableRealtimeSync={Boolean(sharedConversationId)}
      />
    </div>
  );
};

export default Index;
