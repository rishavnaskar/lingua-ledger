import type { Metadata } from "next";
import "./globals.css";
import { SiteHeader } from "@/components/SiteHeader";
import { copy } from "@/lib/copy";

export const metadata: Metadata = {
  title: { default: copy.site.name, template: `%s · ${copy.site.name}` },
  description: copy.site.description,
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body className="flex min-h-screen flex-col bg-white font-sans text-ink antialiased">
        <SiteHeader />
        <main className="mx-auto w-full max-w-[1440px] flex-1 px-4 py-6 sm:px-6 sm:py-8 lg:px-8">{children}</main>
        <footer className="border-t border-line">
          <div className="mx-auto max-w-[1440px] px-4 py-5 text-xs text-muted sm:px-6 lg:px-8">{copy.site.footer}</div>
        </footer>
      </body>
    </html>
  );
}
