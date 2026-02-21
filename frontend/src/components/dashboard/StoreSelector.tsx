import { useStore } from "@/context/StoreContext";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Building2 } from "lucide-react";

export function StoreSelector() {
  const { currentStoreId, setCurrentStoreId, stores } = useStore();

  console.log("StoreSelector - stores:", stores, "currentStoreId:", currentStoreId);

  if (stores.length === 0) {
    return (
      <Select value="" onValueChange={() => {}} disabled>
        <SelectTrigger className="w-[220px] bg-card border-border">
          <Building2 className="mr-2 h-4 w-4 text-muted-foreground" />
          <SelectValue placeholder="No stores available" />
        </SelectTrigger>
      </Select>
    );
  }

  return (
    <Select value={currentStoreId || ""} onValueChange={setCurrentStoreId}>
      <SelectTrigger className="w-[220px] bg-card border-border">
        <Building2 className="mr-2 h-4 w-4 text-muted-foreground" />
        <SelectValue placeholder="Select a store" />
      </SelectTrigger>
      <SelectContent>
        {stores.map((store) => (
          <SelectItem key={store.id} value={store.id}>
            <div className="flex flex-col items-start">
              <span className="font-medium">{store.name}</span>
              {store.location && (
                <span className="text-xs text-muted-foreground">{store.location}</span>
              )}
            </div>
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
