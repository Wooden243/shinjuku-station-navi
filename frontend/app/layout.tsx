import type { Metadata } from "next";

import "maplibre-gl/dist/maplibre-gl.css";
import "./globals.css";

export const metadata: Metadata = {
  title: "新宿地下ナビ | Shinjuku Open Nav",
  description:
    "東京都オープンデータを用いて、新宿駅の改札から出口までを階層別2D地図で案内します。",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="ja">
      <body>{children}</body>
    </html>
  );
}
