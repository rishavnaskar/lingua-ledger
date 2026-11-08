"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { copy } from "@/lib/copy";
import { cn } from "@/lib/format";

const links = [
  { href: "/", label: copy.site.nav.workbench },
  { href: "/metrics", label: copy.site.nav.evidence },
  { href: "/about", label: copy.site.nav.about },
];

export function SiteHeader() {
  const pathname = usePathname();
  return (
    <header className="z-30 border-b border-line bg-white/95 backdrop-blur md:sticky md:top-0">
      <div className="mx-auto flex max-w-[1440px] flex-wrap items-center gap-x-6 gap-y-2 px-4 py-3 sm:px-6 lg:px-8">
        <Link href="/" className="text-lg font-semibold tracking-tight text-ink">
          {copy.site.name}
        </Link>
        <nav aria-label={copy.site.navLabel} className="flex items-center gap-1 text-sm">
          {links.map((l) => {
            const active = l.href === "/" ? pathname === "/" : pathname.startsWith(l.href);
            return (
              <Link
                key={l.href}
                href={l.href}
                aria-current={active ? "page" : undefined}
                className={cn(
                  "rounded-lg px-3 py-1.5 transition-colors",
                  active ? "bg-paper font-medium text-ink" : "text-muted hover:text-ink",
                )}
              >
                {l.label}
              </Link>
            );
          })}
        </nav>
        <span className="ml-auto rounded-full border border-line px-2.5 py-1 text-xs whitespace-nowrap text-muted">
          {copy.site.tag}
        </span>
      </div>
    </header>
  );
}
