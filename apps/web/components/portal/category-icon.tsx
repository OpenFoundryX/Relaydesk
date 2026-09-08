import {
  BookOpen,
  ChartBar,
  CreditCard,
  Folder,
  LifeBuoy,
  Mail,
  Plug,
  Rocket,
  Settings,
  Shield,
  Smartphone,
  Users,
} from "lucide-react";

/**
 * The icon on a collection's card.
 *
 * A stored icon is a *name*, never markup, and this table is the only place
 * a name becomes a component -- an author cannot put an SVG on a page
 * anonymous visitors read. The names match `CATEGORY_ICONS` in
 * `relaydesk.services.kb_categories`, which refuses anything outside the
 * set; this table falls back to a folder anyway, because a collection
 * created before an icon was chosen has none and a card with a hole in it
 * would be worse than a generic one.
 */
const ICONS = {
  "book-open": BookOpen,
  rocket: Rocket,
  "credit-card": CreditCard,
  settings: Settings,
  users: Users,
  mail: Mail,
  plug: Plug,
  shield: Shield,
  "life-buoy": LifeBuoy,
  smartphone: Smartphone,
  "chart-bar": ChartBar,
  folder: Folder,
} as const;

export function CategoryIcon({
  name,
  className,
}: {
  name: string;
  className?: string;
}) {
  const Icon = ICONS[name as keyof typeof ICONS] ?? Folder;
  return <Icon className={className} aria-hidden />;
}
