// ControlPanel: the left "field notebook". Brand + health, persona presets,
// the 5 preference sliders, the distance budget, and a status line. Pure
// presentational — all state lives in App; this just renders + emits changes.

import type { Health, Persona, Prefs } from "../types";
import { PREF_KEYS, PREF_LABELS } from "../types";
import { PersonaPicker } from "./PersonaPicker";

type Props = {
  health: Health | null;
  personas: Persona[];
  personaId: string | null;
  prefs: Prefs;
  budgetKm: number;
  hasStart: boolean;
  loading: boolean;
  onPickPersona: (p: Persona) => void;
  onChangePrefs: (next: Prefs) => void;
  onChangeBudget: (km: number) => void;
};

export function ControlPanel({
  health,
  personas,
  personaId,
  prefs,
  budgetKm,
  hasStart,
  loading,
  onPickPersona,
  onChangePrefs,
  onChangeBudget,
}: Props) {
  const setPref = (key: keyof Prefs, value: number) =>
    onChangePrefs({ ...prefs, [key]: value });

  return (
    <>
      <header className="brand">
        <p className="brand__mark">TrailForge · 探索辅助</p>
        <h1 className="brand__title">北京登山路线探索</h1>
        <p className="brand__sub">拨偏好 · 点起点 · 看几条不同风格的路线即时生成</p>
        <HealthBadge health={health} />
      </header>

      <section className="panel">
        <p className="panel__label">
          登山者画像 <span>可选预设</span>
        </p>
        <p className="panel__hint">
          选一个登山者作起点偏好，也可直接拖下面的滑块。
        </p>
        <PersonaPicker
          personas={personas}
          personaId={personaId}
          onPick={onPickPersona}
        />
      </section>

      <section className="panel">
        <p className="panel__label">偏好</p>
        {PREF_KEYS.map((key) => (
          <div className="slider" key={key}>
            <div className="slider__head">
              <span className="slider__name">{PREF_LABELS[key]}</span>
              <span className="slider__val">{prefs[key].toFixed(2)}</span>
            </div>
            <input
              type="range"
              min={0}
              max={1}
              step={0.05}
              value={prefs[key]}
              onChange={(e) => setPref(key, Number(e.target.value))}
              aria-label={PREF_LABELS[key]}
            />
          </div>
        ))}
      </section>

      <section className="panel">
        <div className="slider__head">
          <span className="panel__label" style={{ margin: 0 }}>
            目标里程
          </span>
          <span className="budget__val">{budgetKm.toFixed(1)} km</span>
        </div>
        <input
          type="range"
          min={1}
          max={15}
          step={0.5}
          value={budgetKm}
          onChange={(e) => onChangeBudget(Number(e.target.value))}
          aria-label="目标里程"
          style={{ marginTop: 8 }}
        />
      </section>

      <section className="panel">
        <StatusLine hasStart={hasStart} loading={loading} />
      </section>
    </>
  );
}

function HealthBadge({ health }: { health: Health | null }) {
  if (!health) {
    return (
      <div className="health">
        <span className="health__dot" />
        连接后端中…
      </div>
    );
  }
  return (
    <div className="health">
      <span className="health__dot health__dot--ok" />
      后端就绪 · {health.n_segments.toLocaleString()} 段 · {health.n_personas} 画像
    </div>
  );
}

function StatusLine({
  hasStart,
  loading,
}: {
  hasStart: boolean;
  loading: boolean;
}) {
  if (loading) {
    return (
      <div className="status">
        <span className="spinner" />
        正在生成候选路线…
      </div>
    );
  }
  if (!hasStart) {
    return <div className="status status--prompt">↘ 在地图上点一个起点开始</div>;
  }
  return <div className="status">拖动滑块即时重算 · 共享同一起点</div>;
}
