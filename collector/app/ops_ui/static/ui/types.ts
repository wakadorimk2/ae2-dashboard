export type Kind = "item" | "fluid" | "gas";
// Dashboard API uses plural keys; UI prefers Kind (singular).
export type KindKey = "items" | "fluids" | "gases";
export type KindMap<T> = { [K in Kind]: T };
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

// UI-side view model (future-facing, separate from DashboardData).
export type UiMeta = Pick<DashboardData, "source" | "ts"> & {
  ageSec?: number;
  timeText?: string;
};

export type UiTopFlatEntry = {
  raw_name: string;
  display_name: string;
  amount: number;
  growth: number;
  decrease: number;
  net: number;
};

export type UiTopFlat = KindMap<UiTopFlatEntry[]>;

export type UiListGroup = {
  amount: Entry[];
  growth: Entry[];
  decrease: Entry[];
};

export type UiLists = KindMap<UiListGroup>;

export type UiHeatmapEntry = {
  raw: string;
  name: string;
  amount: number;
  delta: number;
  entry: UiTopFlatEntry;
};

export type UiHeatmap = {
  kind: Kind;
  entries: UiHeatmapEntry[];
};

export type UiModel = {
  meta?: UiMeta;
  kind: Kind;
  topFlat?: UiTopFlat;
  heatmap?: UiHeatmap;
  lists?: UiLists;
};
