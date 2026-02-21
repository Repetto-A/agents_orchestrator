import { StockProduct } from "@/types/inventory";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { TrendingUp, TrendingDown, Minus, Package } from "lucide-react";
import { cn } from "@/lib/utils";
import { Skeleton } from "@/components/ui/skeleton";

interface StockTableProps {
  products: StockProduct[];
  loading?: boolean;
}

function TrendIcon({ trend }: { trend: StockProduct["sales_trend"] }) {
  switch (trend) {
    case "increasing":
      return <TrendingUp className="h-4 w-4 text-success" />;
    case "decreasing":
      return <TrendingDown className="h-4 w-4 text-destructive" />;
    default:
      return <Minus className="h-4 w-4 text-muted-foreground" />;
  }
}

function DaysLeftBadge({ days, isCritical }: { days: number | null | undefined; isCritical: boolean }) {
  if (days === null || days === undefined) {
    return <Badge variant="outline">N/A</Badge>;
  }

  if (isCritical || days <= 7) {
    return (
      <Badge variant="destructive" className="font-medium">
        {days} days
      </Badge>
    );
  }

  if (days <= 30) {
    return (
      <Badge className="bg-warning text-warning-foreground font-medium">
        {days} days
      </Badge>
    );
  }

  return (
    <Badge variant="outline" className="text-success border-success font-medium">
      {days} days
    </Badge>
  );
}

export function StockTable({ products, loading }: StockTableProps) {
  if (loading) {
    return (
      <Card className="animate-fade-in">
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Package className="h-5 w-5" />
            Stock Overview
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-3">
            {[...Array(5)].map((_, i) => (
              <Skeleton key={i} className="h-12 w-full" />
            ))}
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card className="animate-fade-in shadow-soft">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-lg font-semibold">
          <Package className="h-5 w-5 text-primary" />
          Stock Overview
        </CardTitle>
      </CardHeader>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/50">
              <TableHead className="font-semibold">Product</TableHead>
              <TableHead className="font-semibold text-right">Stock</TableHead>
              <TableHead className="font-semibold text-right">Avg Daily Sales</TableHead>
              <TableHead className="font-semibold text-center">Trend</TableHead>
              <TableHead className="font-semibold text-center">Days Left</TableHead>
              <TableHead className="font-semibold text-right">Reorder Qty</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {products.map((product) => (
              <TableRow
                key={product.product_id}
                className={cn(
                  "transition-colors",
                  product.is_critical && "bg-destructive/5 hover:bg-destructive/10"
                )}
              >
                <TableCell>
                  <div className="flex flex-col">
                    <span className="font-medium">{product.name || product.product_id}</span>
                    <span className="text-xs text-muted-foreground">{product.product_id}</span>
                  </div>
                </TableCell>
                <TableCell className="text-right font-medium">
                  {product.current_stock.toLocaleString()}
                </TableCell>
                <TableCell className="text-right">
                  {product.avg_daily_sales.toFixed(1)}
                </TableCell>
                <TableCell className="text-center">
                  <div className="flex justify-center">
                    <TrendIcon trend={product.sales_trend} />
                  </div>
                </TableCell>
                <TableCell className="text-center">
                  <DaysLeftBadge
                    days={product.estimated_days_left}
                    isCritical={product.is_critical}
                  />
                </TableCell>
                <TableCell className="text-right font-medium text-primary">
                  +{product.reorder_qty_suggestion}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
