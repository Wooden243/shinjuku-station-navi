import type { Metadata, Viewport } from "next";

import { PwaClient } from "@/components/PwaClient";

import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "新宿地下ナビ | Shinjuku Open Nav",
  description: "東京都オープンデータを用いた、新宿駅の改札から出口までの階層別経路案内。",
  applicationName: "新宿地下ナビ",
  manifest: "/manifest.webmanifest",
  appleWebApp: { capable: true, statusBarStyle: "default", title: "新宿地下ナビ" },
  icons: {
    icon: [{ url: "/icons/icon-192.png", sizes: "192x192" }, { url: "/icons/icon-512.png", sizes: "512x512" }],
    apple: "/icons/apple-touch-icon.png",
  },
};

export const viewport: Viewport = {
  width: "device-width",
  initialScale: 1,
  viewportFit: "cover",
  themeColor: "#102f45",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return <html lang="ja"><body>{children}<PwaClient /></body></html>;
}
