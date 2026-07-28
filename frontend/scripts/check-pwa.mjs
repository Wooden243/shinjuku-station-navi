import { access, readFile } from "node:fs/promises";

const manifest = JSON.parse(await readFile("public/manifest.webmanifest", "utf8"));
if (manifest.display !== "standalone") throw new Error("manifest display must be standalone");
for (const size of ["192x192", "512x512"]) {
  if (!manifest.icons.some((icon) => icon.sizes === size)) throw new Error(`missing icon ${size}`);
}
if (!manifest.icons.some((icon) => icon.purpose === "maskable")) throw new Error("missing maskable icon");
await Promise.all(["public/sw.js", "public/offline.html", "public/icons/icon-192.png", "public/icons/icon-512.png", "public/icons/icon-maskable-512.png"].map(access));
console.log("PWA assets: OK");
