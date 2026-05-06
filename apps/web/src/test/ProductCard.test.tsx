import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ProductCard } from "@/features/catalog/components/ProductCard";
import type { Product } from "@/shared/api/contracts";

const fixture: Product = {
  id: "test-product-1",
  slug: "test-product",
  name: "Altitude Shell Jacket",
  brand: "Northbound Goods",
  category: "outerwear",
  price: 220,
  rating: 4.6,
  reviewCount: 128,
  image: "https://placehold.co/400",
  description: "Featherweight technical shell.",
  features: [],
  badges: [],
  inventoryStatus: "in-stock",
  personalizationTags: [],
};

describe("ProductCard", () => {
  it("renders product content", () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ProductCard product={fixture} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText(fixture.name)).toBeInTheDocument();
    expect(screen.getByText(fixture.brand)).toBeInTheDocument();
  });
});
