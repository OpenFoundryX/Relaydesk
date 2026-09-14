import Link from "next/link";

import { cn } from "@/lib/utils";

/**
 * Steep's only button geometry: a fully rounded lozenge at 9999px, 16px Sohne
 * at regular weight, 20px of horizontal padding, and no shadow.
 *
 * The filled and ghost variants share that geometry on purpose so a pair reads
 * as matched on the same baseline -- the style reference asks for the ghost
 * beside every filled primary. Not the console's `Button`, which is a 6px
 * radius and a different type scale.
 */
export function PillLink({
  href,
  variant = "filled",
  className,
  children,
}: {
  href: string;
  variant?: "filled" | "ghost";
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "inline-flex h-11 items-center justify-center gap-2 rounded-full border px-5 text-[16px] font-normal transition-colors",
        variant === "filled"
          ? "border-ink-black bg-ink-black text-paper-white hover:bg-[#2a2d31]"
          : "border-ink-black bg-transparent text-ink-black hover:bg-mist-gray",
        className,
      )}
    >
      {children}
    </Link>
  );
}

/**
 * The lowest-emphasis interactive element. The arrow is part of the label
 * rather than a separate icon, and the underline appears only on hover.
 */
export function ArrowLink({
  href,
  className,
  children,
}: {
  href: string;
  className?: string;
  children: React.ReactNode;
}) {
  return (
    <Link
      href={href}
      className={cn(
        "group inline-flex items-center gap-1.5 text-[16px] font-normal text-ink-black no-underline hover:underline",
        className,
      )}
    >
      {children}{" "}
      <span
        aria-hidden
        className="transition-transform duration-200 ease-out group-hover:translate-x-1"
      >
        →
      </span>
    </Link>
  );
}
