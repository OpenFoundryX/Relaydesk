import Link from "next/link";
import { ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";

export function PortalActions() {
  return (
    <>
      <Button asChild variant="secondary" size="sm">
        <Link href="/submit-ticket" target="_blank">
          <ExternalLink />
          Preview
        </Link>
      </Button>
      <Button variant="primary" size="sm">
        Publish
      </Button>
    </>
  );
}
