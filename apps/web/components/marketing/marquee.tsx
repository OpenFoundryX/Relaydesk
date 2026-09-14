import { BrandIcon, type BrandSlug } from "@/components/brand-icons";
import { cn } from "@/lib/utils";

export type MarqueeItem = { label: string; brand: BrandSlug };

/**
 * A continuously scrolling strip of logo chips.
 *
 * The list is rendered twice and the track translates exactly -50%, so the
 * moment the first copy leaves the viewport the second copy is sitting where
 * it started and the loop has no visible seam. Pure CSS: no observer, no
 * requestAnimationFrame, and nothing that would make this a client component.
 *
 * The duplicate is `aria-hidden` so a screen reader hears the list once.
 */
export function Marquee({
  items,
  className,
}: {
  items: MarqueeItem[];
  className?: string;
}) {
  return (
    <div className={cn("marquee-mask overflow-hidden", className)}>
      <div className="flex w-max animate-carousel gap-x-4 will-change-transform">
        <Row items={items} />
        <Row items={items} aria-hidden />
      </div>
    </div>
  );
}

function Row({
  items,
  ...rest
}: { items: MarqueeItem[] } & React.HTMLAttributes<HTMLUListElement>) {
  return (
    <ul className="flex shrink-0 gap-x-4" {...rest}>
      {items.map((item) => (
        <li
          key={item.label}
          className="flex items-center gap-2.5 whitespace-nowrap rounded-full bg-mist-gray py-2.5 pl-3 pr-5"
        >
          <span className="flex size-7 shrink-0 items-center justify-center rounded-full bg-paper-white">
            <BrandIcon brand={item.brand} className="size-4" />
          </span>
          <span className="text-[15px] font-w450 text-ink-black">
            {item.label}
          </span>
        </li>
      ))}
    </ul>
  );
}
