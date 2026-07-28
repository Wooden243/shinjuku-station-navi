import type { FacilityCategory } from "@/lib/types";

export const FACILITY_META: Record<FacilityCategory, { label: string; symbol: string; color: string }> = {
  restaurant: { label: "飲食店", symbol: "食", color: "#D55E00" },
  convenience_store: { label: "コンビニ", symbol: "コ", color: "#0072B2" },
  cafe: { label: "カフェ", symbol: "珈", color: "#A05A2C" },
  drugstore: { label: "薬局", symbol: "薬", color: "#009E73" },
  atm: { label: "ATM", symbol: "￥", color: "#0072B2" },
  toilet: { label: "トイレ", symbol: "WC", color: "#CC79A7" },
  coin_locker: { label: "ロッカー", symbol: "荷", color: "#E69F00" },
  information: { label: "案内所", symbol: "i", color: "#0072B2" },
  public_phone: { label: "公衆電話", symbol: "☎", color: "#56B4E9" },
  elevator: { label: "エレベーター", symbol: "EV", color: "#009E73" },
  escalator: { label: "エスカレーター", symbol: "ES", color: "#E69F00" },
  stairs: { label: "階段", symbol: "階", color: "#666666" },
  meeting_point: { label: "待ち合わせ", symbol: "待", color: "#CC79A7" },
  shop: { label: "店舗", symbol: "店", color: "#D55E00" },
  other: { label: "その他", symbol: "施", color: "#777777" },
};

export const DEFAULT_FACILITY_CATEGORIES = new Set<FacilityCategory>([
  "restaurant", "convenience_store", "cafe", "drugstore", "atm", "toilet",
  "coin_locker", "information", "public_phone", "elevator", "meeting_point", "shop",
]);
