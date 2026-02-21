import { StoreSelector } from "./StoreSelector";
import { useStore } from "@/context/StoreContext";
import { LayoutDashboard, Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

export function DashboardHeader() {
  const { currentStore } = useStore();

  return (
    <header className="sticky top-0 z-40 border-b bg-card/95 backdrop-blur supports-[backdrop-filter]:bg-card/60">
      <div className="flex h-16 items-center justify-between px-6">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="p-2 rounded-lg bg-primary/10">
              <LayoutDashboard className="h-5 w-5 text-primary" />
            </div>
            <div>
              <h1 className="text-lg font-semibold">Inventory Dashboard</h1>
              {currentStore && (
                <p className="text-xs text-muted-foreground">
                  {currentStore.name} • {currentStore.location}
                </p>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-4">
          <StoreSelector />
          <Button variant="ghost" size="icon" className="relative">
            <Bell className="h-5 w-5" />
            <Badge className="absolute -top-1 -right-1 h-5 w-5 p-0 flex items-center justify-center text-[10px]">
              2
            </Badge>
          </Button>
        </div>
      </div>
    </header>
  );
}
