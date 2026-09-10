export type User = {
  id: string;
  username: string;
  name: string;
  role: "admin" | "member";
  team_name?: string;
};
export type Metrics = {
  views: number | null;
  likes: number | null;
  comments: number | null;
  shares: number | null;
  saves: number | null;
};
export type Frame = {
  time: number;
  file: string;
  brightness: number;
  change: number | null;
  description: string;
  method: string;
};
export type Segment = {
  start: number;
  end: number;
  text: string;
  role: string;
  analysis: string;
  emotion: number | null;
};
export type Analysis = {
  mode: string;
  model?: string;
  summary: string;
  hook: { quote: string; analysis: string };
  factors: {
    title: string;
    evidence: string;
    explanation: string;
    time: number | null;
  }[];
  structure: Segment[];
  audience: string;
  formula: string;
  suggestions: string[];
  limitations: string[];
  copywriting: {
    title_analysis: string;
    density: number;
    opening: string;
    rewrite: string[];
  };
};
export type Result = {
  title?: string;
  author?: string;
  platform?: string;
  duration?: number;
  metrics?: Metrics;
  analysis?: Analysis;
  cover_file?: string;
  video_file?: string;
  playback_file?: string;
  frames?: Frame[];
  width?: number;
  height?: number;
  source_url?: string;
  published_at?: number;
  collected_at?: number;
  tags?: string[];
  warnings?: string[];
  imported?: boolean;
  frame_interval?: number;
  ratios?: Record<string, number | null>;
  transcript?: {
    text: string;
    segments: { start: number; end: number; text: string }[];
  timing: string;
  language?: string;
  note: string;
  };
  comments?: {
    id: string;
    author: string;
    text: string;
    likes: number | null;
    timestamp?: number;
    intent?: string;
  }[];
  comments_note?: string;
  comment_insights?: {
    sample_size: number;
    method: string;
    intents: { label: string; count: number; example: string }[];
    keywords: { word: string; count: number }[];
  };
};
export type Job = {
  id: string;
  url: string;
  owner: string;
  owner_name: string;
  status: string;
  stage: string;
  created: number;
  updated: number;
  error: string | null;
  result: Result;
};
