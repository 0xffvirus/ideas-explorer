import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";
import { SiteHeader } from "@/components/site/site-header";
import { PaletteHost } from "@/components/site/palette-host";

export const metadata: Metadata = {
  title: { default: "Idea Forge", template: "%s · Idea Forge" },
  description: "Turn a rough business idea into a validated, sourced, decision-ready analysis.",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="en">
      <body className="min-h-dvh">
        <a className="skip-link" href="#main">
          Skip to content
        </a>
        <Providers>
          <SiteHeader />
          <PaletteHost />
          {children}
        </Providers>
      </body>
    </html>
  );
}
