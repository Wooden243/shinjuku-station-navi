import { mkdir } from "node:fs/promises";
import path from "node:path";
import sharp from "sharp";

const output = path.resolve("public/icons");
await mkdir(output, { recursive: true });

function source(size, maskable = false) {
  const inset = maskable ? Math.round(size * 0.2) : Math.round(size * 0.08);
  const content = size - inset * 2;
  return Buffer.from(`<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}" xmlns="http://www.w3.org/2000/svg">
  <rect width="${size}" height="${size}" rx="${maskable ? 0 : size * 0.18}" fill="#102f45"/>
  <path d="M${inset + content * .12} ${inset + content * .72} L${inset + content * .42} ${inset + content * .44} L${inset + content * .62} ${inset + content * .56} L${inset + content * .88} ${inset + content * .24}" fill="none" stroke="#56B4E9" stroke-width="${size * .07}" stroke-linecap="round" stroke-linejoin="round"/>
  <circle cx="${inset + content * .12}" cy="${inset + content * .72}" r="${size * .065}" fill="#009E73" stroke="white" stroke-width="${size * .025}"/>
  <circle cx="${inset + content * .88}" cy="${inset + content * .24}" r="${size * .065}" fill="#D55E00" stroke="white" stroke-width="${size * .025}"/>
  <text x="${size / 2}" y="${inset + content * .9}" text-anchor="middle" fill="white" font-size="${size * .15}" font-weight="800" font-family="sans-serif">新宿</text>
  </svg>`);
}

await sharp(source(192)).png().toFile(path.join(output, "icon-192.png"));
await sharp(source(512)).png().toFile(path.join(output, "icon-512.png"));
await sharp(source(512, true)).png().toFile(path.join(output, "icon-maskable-512.png"));
await sharp(source(180)).png().toFile(path.join(output, "apple-touch-icon.png"));
