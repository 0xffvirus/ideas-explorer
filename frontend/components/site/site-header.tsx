import Link from "next/link";
import { Suspense } from "react";
import { PaletteTrigger } from "./palette-trigger";
import { PrimaryNav } from "./primary-nav";

export function SiteHeader() {
  return (
    <header className="site-header">
      <nav className="nav-pill" aria-label="Primary">
        <Link
          href="/"
          className="inline-flex min-h-11 items-center rounded-full px-3 text-base font-bold text-ink no-underline"
        >
          Idea Forge
        </Link>
        <div className="flex items-center gap-2">
          <Suspense
            fallback={
              <ul className="nav-links">
                <li>
                  <Link href="/ideas">Library</Link>
                </li>
              </ul>
            }
          >
            <PrimaryNav />
          </Suspense>
          <PaletteTrigger />
        </div>
      </nav>
    </header>
  );
}
