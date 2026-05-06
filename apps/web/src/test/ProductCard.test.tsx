import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, screen } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";

import { ProductCard } from "@/features/catalog/components/ProductCard";
import { products } from "@/mocks/data/products";

describe("ProductCard", () => {
  it("renders product content", () => {
    const queryClient = new QueryClient();

    render(
      <QueryClientProvider client={queryClient}>
        <MemoryRouter>
          <ProductCard product={products[0]} />
        </MemoryRouter>
      </QueryClientProvider>,
    );

    expect(screen.getByText(products[0].name)).toBeInTheDocument();
    expect(screen.getByText(products[0].brand)).toBeInTheDocument();
  });
});
