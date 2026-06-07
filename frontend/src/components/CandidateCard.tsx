// CandidateCard: one route in the list. Colour bar + dot match the map line
// (assigned by response order via palette.ts). Hover ↔ map highlight is
// two-way. Inline feedback (Module E): "选这条" and/or 1–5 stars POST /feedback.

import { useState } from "react";
import { api } from "../api";
import { candidateCss } from "../palette";
import type { FeedbackIn, RouteCandidate } from "../types";

type Props = {
  candidate: RouteCandidate;
  index: number;
  active: boolean;
  dimmed: boolean;
  context: FeedbackIn["context"];
  onSelect: () => void;
  onHover: (on: boolean) => void;
};

export function CandidateCard({
  candidate,
  index,
  active,
  dimmed,
  context,
  onSelect,
  onHover,
}: Props) {
  const [done, setDone] = useState<{ rating: number | null } | null>(null);
  const [hoverStar, setHoverStar] = useState(0);
  const [busy, setBusy] = useState(false);

  const color = candidateCss(index);

  const submit = (rating: number | null) => {
    if (busy || done) return;
    setBusy(true);
    api
      .feedback({ chosen_index: index, rating, comment: null, context })
      .then(() => setDone({ rating }))
      .catch(() => undefined)
      .finally(() => setBusy(false));
  };

  return (
    <div
      className={`card${active ? " card--active" : ""}${dimmed ? " card--dim" : ""}`}
      style={
        {
          ["--card-color" as string]: color,
          animationDelay: `${index * 45}ms`,
        } as React.CSSProperties
      }
      onMouseEnter={() => onHover(true)}
      onMouseLeave={() => onHover(false)}
      onClick={onSelect}
    >
      <div className="card__top">
        <span className="card__dot" />
        <span className="card__name">路线 {index + 1}</span>
        <span className="card__km">{candidate.length_km.toFixed(1)} km</span>
      </div>

      {candidate.labels.length > 0 && (
        <div className="chips">
          {candidate.labels.map((l, i) => (
            <span className="chip" key={i}>
              {l}
            </span>
          ))}
        </div>
      )}

      <div className="card__meta">
        <span>{candidate.n_segments} 段</span>
        <span>评分 {candidate.score.toFixed(2)}</span>
      </div>

      {!candidate.reachable && (
        <div className="card__unreach">未达目标里程（已尽量延伸）</div>
      )}

      <div className="feedback" onClick={(e) => e.stopPropagation()}>
        {done ? (
          <span className="feedback__done">
            ✓ 已记录{done.rating ? ` · ${done.rating}★` : ""}
          </span>
        ) : (
          <>
            <button
              type="button"
              className="feedback__btn"
              disabled={busy}
              onClick={() => submit(null)}
            >
              选这条
            </button>
            <span
              className="stars"
              onMouseLeave={() => setHoverStar(0)}
              role="radiogroup"
              aria-label="评分"
            >
              {[1, 2, 3, 4, 5].map((n) => (
                <button
                  key={n}
                  type="button"
                  className={`star${n <= hoverStar ? " star--on" : ""}`}
                  onMouseEnter={() => setHoverStar(n)}
                  onClick={() => submit(n)}
                  aria-label={`${n} 星`}
                >
                  ★
                </button>
              ))}
            </span>
          </>
        )}
      </div>
    </div>
  );
}
