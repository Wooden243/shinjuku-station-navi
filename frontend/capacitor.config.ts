import type { CapacitorConfig } from "@capacitor/cli";

const config: CapacitorConfig = {
  appId: "jp.example.shinjukuopennav",
  appName: "新宿地下ナビ",
  webDir: "out",
  server: { androidScheme: "https" },
};

export default config;
