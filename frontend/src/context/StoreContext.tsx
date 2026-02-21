import React, { createContext, useContext, useState, useEffect, ReactNode } from "react";
import type { Store } from "@/types/inventory";
import { getStores } from "@/services/api";

interface StoreContextType {
  currentStoreId: string | null;
  setCurrentStoreId: (id: string | null) => void;
  selectedStoreIds: string[];
  setSelectedStoreIds: (ids: string[]) => void;
  stores: Store[];
  currentStore: Store | null;
}

const StoreContext = createContext<StoreContextType | undefined>(undefined);

export function StoreProvider({ children }: { children: ReactNode }) {
  const [currentStoreId, setCurrentStoreId] = useState<string | null>(null);
  const [selectedStoreIds, setSelectedStoreIds] = useState<string[]>([]);
  const [stores, setStores] = useState<Store[]>([]);

  useEffect(() => {
    async function fetchStores() {
      try {
        const data = await getStores();
        console.log("Fetched stores:", data);
        setStores(data);
        if (data.length > 0) {
          setCurrentStoreId((prev) => prev ?? data[0].id);
        }
      } catch (err) {
        console.error("Failed to fetch stores", err);
      }
    }
    fetchStores();
  }, []);

  const currentStore = stores.find((s) => s.id === currentStoreId) || null;

  return (
    <StoreContext.Provider
      value={{
        currentStoreId,
        setCurrentStoreId,
        selectedStoreIds,
        setSelectedStoreIds,
        stores,
        currentStore,
      }}
    >
      {children}
    </StoreContext.Provider>
  );
}

export function useStore() {
  const context = useContext(StoreContext);
  if (!context) throw new Error("useStore must be used within a StoreProvider");
  return context;
}
