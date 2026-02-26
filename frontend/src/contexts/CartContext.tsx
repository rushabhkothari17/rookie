import React, { createContext, useContext, useEffect, useState } from "react";

export type CartItem = {
  product_id: string;
  quantity: number;
  inputs: Record<string, any>;
  price_override?: number;
  // Validation metadata (populated at add-time from product data)
  pricing_type?: string;    // "internal" | "external" | "enquiry"
  currency?: string;
  is_subscription?: boolean;
};

/** The "checkout group" — what kind of checkout flow the cart represents */
type CartGroupType = "one_time" | "subscription" | "enquiry" | "external";

const getGroupType = (item: CartItem): CartGroupType => {
  if (item.pricing_type === "external") return "external";
  if (item.pricing_type === "enquiry") return "enquiry";
  if (item.is_subscription) return "subscription";
  return "one_time";
};

const groupLabel = (t: CartGroupType) => {
  if (t === "one_time") return "one-time";
  return t;
};

type CartContextType = {
  items: CartItem[];
  /** Returns null on success, or an error message string if validation fails */
  addItem: (item: CartItem) => string | null;
  updateItem: (productId: string, updates: Partial<CartItem>) => void;
  removeItem: (productId: string) => void;
  clear: () => void;
};

const CartContext = createContext<CartContextType | undefined>(undefined);

const STORAGE_KEY = "aa_cart_items";

export const CartProvider = ({ children }: { children: React.ReactNode }) => {
  const [items, setItems] = useState<CartItem[]>(() => {
    try {
      const stored = localStorage.getItem(STORAGE_KEY);
      return stored ? JSON.parse(stored) : [];
    } catch { return []; }
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(items));
  }, [items]);

  const addItem = (item: CartItem): string | null => {
    // If the same product is already in cart — just update it
    const existing = items.find((i) => i.product_id === item.product_id);
    if (existing) {
      setItems((prev) =>
        prev.map((i) => i.product_id === item.product_id ? { ...i, ...item } : i)
      );
      return null;
    }

    // Validate against existing cart items
    if (items.length > 0) {
      const existingType = getGroupType(items[0]);
      const newType = getGroupType(item);

      if (existingType !== newType) {
        return `Your cart already contains a ${groupLabel(existingType)} product. Please remove it before adding a ${groupLabel(newType)} product — only one type of product is allowed per checkout.`;
      }

      const existingCurrency = items[0].currency;
      if (existingCurrency && item.currency && existingCurrency !== item.currency) {
        return `Your cart contains ${existingCurrency} products. All items must use the same currency — please remove existing items before adding ${item.currency} products.`;
      }
    }

    setItems((prev) => [...prev, item]);
    return null;
  };

  const updateItem = (productId: string, updates: Partial<CartItem>) => {
    setItems((prev) =>
      prev.map((item) =>
        item.product_id === productId ? { ...item, ...updates } : item,
      ),
    );
  };

  const removeItem = (productId: string) => {
    setItems((prev) => prev.filter((item) => item.product_id !== productId));
  };

  const clear = () => setItems([]);

  return (
    <CartContext.Provider
      value={{ items, addItem, updateItem, removeItem, clear }}
    >
      {children}
    </CartContext.Provider>
  );
};

export const useCart = () => {
  const context = useContext(CartContext);
  if (!context) {
    throw new Error("useCart must be used within CartProvider");
  }
  return context;
};
