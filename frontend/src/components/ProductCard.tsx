import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

const fmtPrice = (amount: number, currency = "USD") =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, minimumFractionDigits: 0, maximumFractionDigits: 2 }).format(amount);

const getPriceLabel = (product: any) => {
  const currency = product.currency || "USD";
  if (product.base_price) {
    return fmtPrice(product.base_price, currency);
  }
  if (product.pricing_type === "tiered") {
    const prices = (product.pricing_rules?.variants || []).map((v: any) => v.price);
    if (prices.length) {
      return fmtPrice(Math.min(...prices), currency);
    }
  }
  return "Calculator";
};

export default function ProductCard({ product }: { product: any }) {
  const priceLabel = getPriceLabel(product);

  return (
    <Card
      className="transition-transform transition-shadow duration-300 hover:-translate-y-1 hover:shadow-lg"
      data-testid={`product-card-${product.id}`}
    >
      <CardHeader className="space-y-2">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-400" data-testid={`product-card-category-${product.id}`}>
          {product.category}
        </div>
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900" data-testid={`product-card-name-${product.id}`}>
              {product.name}
            </h3>
            <p className="text-sm text-slate-600" data-testid={`product-card-tagline-${product.id}`}>
              {product.tagline}
            </p>
          </div>
          <ArrowUpRight className="text-slate-400" size={18} />
        </div>
      </CardHeader>
      <CardContent className="flex items-center justify-between">
        <div className="text-base font-semibold text-slate-900" data-testid={`product-card-price-${product.id}`}>
          {priceLabel}
        </div>
        <Link
          to={`/product/${product.id}`}
          className="text-sm text-blue-600 hover:text-blue-700"
          data-testid={`product-card-view-${product.id}`}
        >
          View details
        </Link>
      </CardContent>
    </Card>
  );
}
