import { describe, expect, it } from "vitest";
import { hostname, safeExternalUrl, truncate } from "./format";
import { slugify } from "./download";

describe("safeExternalUrl", () => {
  it("accepts http and https URLs", () => {
    expect(safeExternalUrl("https://example.com/a")).toBe("https://example.com/a");
    expect(safeExternalUrl("http://example.com")).toBe("http://example.com/");
  });

  it("rejects scheme-less, non-http and empty values", () => {
    expect(safeExternalUrl("gorilladesk.com")).toBeUndefined();
    expect(safeExternalUrl("javascript:alert(1)")).toBeUndefined();
    expect(safeExternalUrl("data:text/html,x")).toBeUndefined();
    expect(safeExternalUrl(null)).toBeUndefined();
    expect(safeExternalUrl("")).toBeUndefined();
  });
});

describe("hostname", () => {
  it("strips www and survives invalid URLs", () => {
    expect(hostname("https://www.statista.com/outlook")).toBe("statista.com");
    expect(hostname("not a url")).toBe("not a url");
  });
});

describe("slugify", () => {
  it("produces safe download filenames", () => {
    expect(slugify("Dog walking marketplace!")).toBe("dog-walking-marketplace");
    expect(slugify("../../etc/passwd")).toBe("etcpasswd");
    expect(slugify("")).toBe("idea");
  });
});

describe("truncate", () => {
  it("adds an ellipsis only when needed", () => {
    expect(truncate("short", 10)).toBe("short");
    expect(truncate("abcdefghijk", 6)).toBe("abcde…");
  });
});
