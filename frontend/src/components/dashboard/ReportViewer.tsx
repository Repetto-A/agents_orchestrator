import { useEffect, useMemo, useState } from "react";
import { ReportData } from "@/types/inventory";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { FileText, Clock, BarChart3 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { ResponsiveContainer, BarChart, Bar, XAxis, YAxis, Tooltip } from "recharts";
import { cn } from "@/lib/utils";

interface ReportViewerProps {
  reports: ReportData[];
  loading?: boolean;
}

export function ReportViewer({ reports, loading }: ReportViewerProps) {
  const [activeReportIndex, setActiveReportIndex] = useState(0);

  useEffect(() => {
    if (!reports.length) {
      setActiveReportIndex(0);
      return;
    }
    setActiveReportIndex((prev) => Math.min(prev, reports.length - 1));
  }, [reports.length]);

  const activeReport = reports[activeReportIndex];

  const renderValue = (value: unknown) => {
    if (value === null || value === undefined) return "-";
    if (typeof value === "string" || typeof value === "number" || typeof value === "boolean") return String(value);
    return JSON.stringify(value);
  };

  const toNumeric = (value: unknown): number | null => {
    if (typeof value === "number") return Number.isFinite(value) ? value : null;
    if (typeof value !== "string") return null;
    const cleaned = value.replace(/[^0-9.-]/g, "");
    if (!cleaned) return null;
    const parsed = Number(cleaned);
    return Number.isFinite(parsed) ? parsed : null;
  };

  const chartData = useMemo(() => {
    const rows = activeReport?.table || [];
    if (!rows.length) return [];

    const labelCandidates = ["producto", "product", "product_name", "name", "product_id"];
    const valuePriority = ["ingresos_7_dias", "total_revenue", "revenue", "ventas_7_dias", "total_sold", "stock_actual", "current_stock"];

    return rows
      .slice(0, 6)
      .map((row) => {
        const labelKey = labelCandidates.find((key) => typeof row[key] === "string");
        const label = labelKey ? String(row[labelKey]) : "Item";

        let value: number | null = null;
        for (const key of valuePriority) {
          value = toNumeric(row[key]);
          if (value !== null) break;
        }
        if (value === null) {
          const firstNumeric = Object.values(row).map(toNumeric).find((n) => n !== null);
          value = firstNumeric ?? 0;
        }

        return { label, value };
      })
      .filter((item) => item.value > 0);
  }, [activeReport]);

  if (loading) {
    return (
      <Card className="animate-fade-in">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <FileText className="h-5 w-5" />
            AI Reports
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[...Array(3)].map((_, i) => (
              <Skeleton key={i} className="h-16 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="animate-fade-in shadow-soft">
      <CardHeader className="pb-3 border-b bg-gradient-to-r from-primary/10 via-primary/5 to-transparent">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          <FileText className="h-5 w-5 text-primary" />
          AI Reports
          {reports.length > 0 && (
            <Badge variant="outline" className="ml-2">
              {reports.length} generated
            </Badge>
          )}
        </CardTitle>
      </CardHeader>
      <CardContent className="p-4">
        {reports.length === 0 ? (
          <div className="text-center py-10 text-muted-foreground">
            <FileText className="h-12 w-12 mx-auto mb-3 opacity-50" />
            <p>No reports generated yet</p>
            <p className="text-sm">Ask the assistant for a KPI report</p>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="flex flex-wrap gap-2">
              {reports.map((report, index) => (
                <button
                  key={`${report.generatedAt}-${index}`}
                  type="button"
                  onClick={() => setActiveReportIndex(index)}
                  className={cn(
                    "rounded-md border px-3 py-1.5 text-xs transition-colors",
                    activeReportIndex === index ? "border-primary bg-primary/10 text-primary" : "border-border hover:bg-muted"
                  )}
                >
                  <span className="font-medium">{report.type}</span>
                  <span className="ml-2 inline-flex items-center gap-1 text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {new Date(report.generatedAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                  </span>
                </button>
              ))}
            </div>

            {activeReport && (
              <div className="space-y-3 rounded-lg border p-4">
                <div>
                  <h4 className="text-base font-semibold">{activeReport.title}</h4>
                  {activeReport.summary && <p className="text-sm text-muted-foreground mt-1">{activeReport.summary}</p>}
                </div>

                {activeReport.kpis && (
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                    {Object.entries(activeReport.kpis).slice(0, 6).map(([key, value]) => (
                      <div key={key} className="rounded-md border bg-muted/30 px-3 py-2 text-sm">
                        <p className="text-xs text-muted-foreground">{key}</p>
                        <p className="font-medium">{renderValue(value)}</p>
                      </div>
                    ))}
                  </div>
                )}

                {chartData.length > 0 && (
                  <div className="rounded-md border p-3">
                    <div className="mb-2 flex items-center gap-1 text-xs font-medium text-muted-foreground">
                      <BarChart3 className="h-3 w-3" />
                      Report chart
                    </div>
                    <div className="h-56">
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={chartData}>
                          <XAxis dataKey="label" tick={{ fontSize: 11 }} interval={0} angle={-15} textAnchor="end" height={44} />
                          <YAxis tick={{ fontSize: 11 }} width={34} />
                          <Tooltip formatter={(value: number) => value.toLocaleString()} />
                          <Bar dataKey="value" fill="hsl(var(--primary))" radius={[5, 5, 0, 0]} />
                        </BarChart>
                      </ResponsiveContainer>
                    </div>
                  </div>
                )}

                {activeReport.table && activeReport.table.length > 0 && (
                  <div className="overflow-x-auto rounded-md border">
                    <table className="w-full text-sm">
                      <thead className="bg-muted/50">
                        <tr>
                          {Object.keys(activeReport.table[0]).slice(0, 5).map((col) => (
                            <th key={col} className="px-3 py-2 text-left font-medium">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {activeReport.table.slice(0, 5).map((row, idx) => (
                          <tr key={idx} className="border-t">
                            {Object.keys(activeReport.table?.[0] || {}).slice(0, 5).map((col) => (
                              <td key={col} className="px-3 py-2">{renderValue(row[col])}</td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
