import { Link } from "react-router-dom";
import { ArrowUpRight } from "lucide-react";
import { Card, CardContent, CardHeader } from "@/components/ui/card";

export default function ProductCard({ product }: { product: any }) {
  const priceLabel = product.base_price
    ? `$${product.base_price.toFixed(2)}`
    : product.pricing_type === "tiered"
      ? "From"
      : "Calculator";

  return (
    <Card
      className="transition-all hover:-translate-y-1 hover:shadow-lg"
      data-testid={`product-card-${product.id}`}
    >
      <CardHeader className="space-y-2">
        <div className="text-xs uppercase tracking-[0.2em] text-slate-400">
          {product.category}
        </div>
        <div className="flex items-start justify-between">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">
              {product.name}
            </h3>
            <p className="text-sm text-slate-600">{product.tagline}</p>
          </div>
          <ArrowUpRight className="text-slate-400" size={18} />
        </div>
      </CardHeader>
      <CardContent className="flex items-center justify-between">
        <div className="text-base font-semibold text-slate-900">{priceLabel}</div>
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
