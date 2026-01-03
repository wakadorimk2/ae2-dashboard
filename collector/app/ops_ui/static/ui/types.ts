export type Kind = "items" | "fluids" | "gases";
export type ViewMode = "heatmap" | "list";
export type HeatmapCount = 40 | 80 | 120;

export type Entry = {
  id: string;
  name: string;
  amount: number;
  growth_per_min: number;
  decrease_per_min: number;
};

export type DashboardData = {
  top?: {
    items?: Entry[];
    fluids?: Entry[];
    gases?: Entry[];
  };
};
