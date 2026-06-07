// PersonaPicker: 5 behaviour-cluster presets. Picking one fills the sliders
// with its `default_prefs`; dragging a slider afterwards clears the selection
// (App treats explicit prefs as authoritative — see resolve_prefs on backend).

import type { Persona } from "../types";

type Props = {
  personas: Persona[];
  personaId: string | null;
  onPick: (p: Persona) => void;
};

export function PersonaPicker({ personas, personaId, onPick }: Props) {
  if (personas.length === 0) return null;
  return (
    <div className="personas">
      {personas.map((p) => (
        <button
          key={p.id}
          type="button"
          className={`persona${p.id === personaId ? " persona--on" : ""}`}
          onClick={() => onPick(p)}
          aria-pressed={p.id === personaId}
        >
          <div className="persona__name">{p.label}</div>
          <div className="persona__desc">{p.description}</div>
          <div className="persona__size">{p.size.toLocaleString()} 条轨迹</div>
        </button>
      ))}
    </div>
  );
}
