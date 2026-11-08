import { cn } from "@/lib/format";

export function Card({
  className,
  children,
  as: Tag = "section",
  ...rest
}: React.HTMLAttributes<HTMLElement> & { as?: "section" | "div" | "article" }) {
  return (
    <Tag className={cn("rounded-2xl bg-paper p-4 sm:p-5", className)} {...rest}>
      {children}
    </Tag>
  );
}

export function CardTitle({
  children,
  icon: Icon,
  aside,
}: {
  children: React.ReactNode;
  icon?: React.ComponentType<{ className?: string; "aria-hidden"?: boolean }>;
  aside?: React.ReactNode;
}) {
  return (
    <div className="mb-3 flex flex-wrap items-center justify-between gap-x-4 gap-y-2">
      <h2 className="flex items-center gap-2 text-sm font-semibold tracking-wide text-ink uppercase">
        {Icon && <Icon className="h-4 w-4 text-navy" aria-hidden />}
        {children}
      </h2>
      {aside}
    </div>
  );
}
