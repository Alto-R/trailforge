// CandidateList: the score-desc candidate cards under the controls. Active =
// hovered, falling back to selected (mirrors the map's activeIdx). When one is
// active the rest dim, so "a few different styles" reads at a glance (MMR).

import { CandidateCard } from "./CandidateCard";
import type { LngLat, Prefs, RouteCandidate } from "../types";

type Props = {
  candidates: RouteCandidate[];
  loading: boolean;
  selectedIdx: number | null;
  hoveredIdx: number | null;
  context: { start: LngLat | null; prefs: Prefs; budget_km: number };
  onSelect: (i: number | null) => void;
  onHover: (i: number | null) => void;
};

export function CandidateList({
  candidates,
  loading,
  selectedIdx,
  hoveredIdx,
  context,
  onSelect,
  onHover,
}: Props) {
  const activeIdx = hoveredIdx ?? selectedIdx;

  if (candidates.length === 0) {
    return (
      <div className="candidates">
        <p className="panel__label" style={{ margin: 0 }}>
          候选路线
        </p>
        <p className="candidates__empty">
          {loading
            ? "正在生成候选路线…"
            : context.start
              ? "该起点附近没找到可行路线，换个点或调大目标里程试试。"
              : "在地图上点一个起点，几条不同风格的候选路线会出现在这里。"}
        </p>
      </div>
    );
  }

  return (
    <div className="candidates">
      <p className="panel__label" style={{ margin: 0 }}>
        候选路线 <span>{candidates.length} 条 · 按相关度排序</span>
      </p>
      {candidates.map((c, i) => (
        <CandidateCard
          key={i}
          candidate={c}
          index={i}
          active={activeIdx === i}
          dimmed={activeIdx !== null && activeIdx !== i}
          context={context}
          onSelect={() => onSelect(selectedIdx === i ? null : i)}
          onHover={(on) => onHover(on ? i : null)}
        />
      ))}
    </div>
  );
}
