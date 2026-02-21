import { SalesResponse } from "@/types/inventory";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { BarChart3, TrendingUp, DollarSign, Award } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
} from "recharts";
import { KPICard } from "./KPICard";

interface SalesOverviewProps {
  data: SalesResponse | null;
  loading?: boolean;
}

export function SalesOverview({ data, loading }: SalesOverviewProps) {
  if (loading) {
    return (
      <div className="space-y-4 animate-fade-in">
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <Skeleton key={i} className="h-32" />
          ))}
        </div>
        <Skeleton className="h-64" />
      </div>
    );
  }

  if (!data) return null;

  const chartData = data.products.map((p) => ({
    name: p.product_name || p.product_id,
    revenue: p.total_revenue,
    trend: p.weekly_trend,
  }));

  const formatCurrency = (value: number) =>
    new Intl.NumberFormat("en-US", {
      style: "currency",
      currency: "USD",
      minimumFractionDigits: 0,
      maximumFractionDigits: 0,
    }).format(value);

  return (
    <div className="space-y-4 animate-slide-up">
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <KPICard
          title="Total Revenue"
          value={formatCurrency(data.summary?.total_revenue || 0)}
          icon={DollarSign}
          trend={{ value: 12.5, label: "vs last week" }}
          variant="success"
        />
        <KPICard
          title="Avg Daily Sales"
          value={data.summary?.avg_daily_sales?.toFixed(1) || "0"}
          subtitle="units per day"
          icon={BarChart3}
          variant="default"
        />
        <KPICard
          title="Top Product"
          value={data.summary?.top_product?.product_name || "N/A"}
          subtitle={
            data.summary?.top_product
              ? `${data.summary.top_product.total_sold} units sold`
              : undefined
          }
          icon={Award}
          variant="warning"
        />
      </div>

      <Card className="shadow-soft">
        <CardHeader className="pb-2">
          <CardTitle className="flex items-center gap-2 text-lg font-semibold">
            <TrendingUp className="h-5 w-5 text-primary" />
            Revenue by Product
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={chartData}>
                <defs>
                  <linearGradient id="colorRevenue" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%" stopColor="hsl(var(--primary))" stopOpacity={0.3} />
                    <stop offset="95%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                  </linearGradient>
                </defs>
                <XAxis
                  dataKey="name"
                  tick={{ fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                />
                <YAxis
                  tick={{ fontSize: 12 }}
                  tickLine={false}
                  axisLine={false}
                  tickFormatter={(value) => `$${(value / 1000).toFixed(0)}k`}
                />
                <Tooltip
                  contentStyle={{
                    background: "hsl(var(--card))",
                    border: "1px solid hsl(var(--border))",
                    borderRadius: "8px",
                    fontSize: "12px",
                  }}
                  formatter={(value: number) => [formatCurrency(value), "Revenue"]}
                />
                <Area
                  type="monotone"
                  dataKey="revenue"
                  stroke="hsl(var(--primary))"
                  strokeWidth={2}
                  fill="url(#colorRevenue)"
                />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
