export type Kind = "item" | "fluid" | "gas";
export type KindKey = "items" | "fluids" | "gases";
export type HeatmapCount = 40 | 80 | 120;
export type Metric = "amount" | "growth" | "decrease";

export type Entry = {
  id: string;
  name: string;
  amount: number;
  growth: number;
  decrease: number;
  raw_name?: string;
  display_name?: string;
};

export type TopByKind = {
  items?: Entry[];
  fluids?: Entry[];
  gases?: Entry[];
};

export type DashboardTop = {
  amount?: TopByKind;
  growth?: TopByKind;
  decrease?: TopByKind;
};

export type DashboardData = {
  top?: DashboardTop;
  source?: string;
  ts?: number;
};
