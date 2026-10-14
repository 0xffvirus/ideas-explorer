"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

export function PrimaryNav() {
  const pathname = usePathname();
  const isLibrary = pathname.startsWith("/ideas");

  return (
    <ul className="nav-links">
      <li>
        <Link href="/ideas" aria-current={isLibrary ? "page" : undefined}>
          Library
        </Link>
      </li>
    </ul>
  );
}
