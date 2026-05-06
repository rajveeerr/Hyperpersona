import { Link } from "react-router-dom";

import type { Category } from "@/shared/api/contracts";
import { tw } from "@/shared/ui/tw";

type CollectionStoryGridProps = {
  categories: Category[];
};

export const CollectionStoryGrid = ({ categories }: CollectionStoryGridProps) => {
  return (
    <section className="grid grid-cols-[1.1fr_0.9fr_0.9fr] gap-5 max-[960px]:grid-cols-1">
      {categories.map((category, index) => (
        <article
          key={category.id}
          className={`flex flex-col justify-between rounded-card border border-outline bg-gradient-to-b from-[rgba(255,252,247,0.94)] to-[rgba(243,234,223,0.86)] p-8 ${index % 3 === 0 ? "min-h-[300px]" : "min-h-[220px]"}`}
        >
          <div className={tw.stackMd}>
            <span className={tw.eyebrow}>{category.name}</span>
            <h2 className={tw.storyTitle}>{category.hero}</h2>
            <p className={tw.muted}>{category.description}</p>
          </div>
          <Link to={`/catalog?category=${category.slug}`} className={tw.buttonGhost}>
            View {category.name}
          </Link>
        </article>
      ))}
    </section>
  );
};
