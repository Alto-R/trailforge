// MapView: deck.gl renders the WebGL layers and owns the camera; a react-map-gl
// (maplibre) carto-positron basemap rides underneath as a child. Layers, bottom
// to top: faint full trail network → one line per candidate → start marker.
// Click empty map = pick start; click a candidate line = select it. The view
// fits the trail bbox once on load and then never auto-moves (stable for demos).

import { useEffect, useMemo, useRef, useState } from "react";
import DeckGL from "@deck.gl/react";
import { WebMercatorViewport, type PickingInfo } from "@deck.gl/core";
import { GeoJsonLayer, ScatterplotLayer } from "@deck.gl/layers";
import { Map } from "react-map-gl/maplibre";
import "maplibre-gl/dist/maplibre-gl.css";
import { candidateColor, TRAIL_COLOR } from "../palette";
import type { LngLat, RouteCandidate } from "../types";

const MAP_STYLE =
  "https://basemaps.cartocdn.com/gl/positron-gl-style/style.json";

type ViewState = {
  longitude: number;
  latitude: number;
  zoom: number;
  pitch: number;
  bearing: number;
};

// Beijing mountain ring — overridden by fitBounds once /trails arrives.
const DEFAULT_VIEW: ViewState = {
  longitude: 116.1,
  latitude: 40.1,
  zoom: 8.5,
  pitch: 0,
  bearing: 0,
};

type Props = {
  trails: GeoJSON.FeatureCollection | null;
  candidates: RouteCandidate[];
  startSnapped: LngLat | null;
  activeIdx: number | null;
  onPickStart: (ll: LngLat) => void;
  onSelectCandidate: (i: number | null) => void;
  onHoverCandidate: (i: number | null) => void;
};

export function MapView({
  trails,
  candidates,
  startSnapped,
  activeIdx,
  onPickStart,
  onSelectCandidate,
  onHoverCandidate,
}: Props) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [viewState, setViewState] = useState<ViewState>(DEFAULT_VIEW);
  const fitted = useRef(false);

  // Fit to the trail network once, using the measured container size.
  useEffect(() => {
    if (!trails || fitted.current) return;
    const b = featureCollectionBounds(trails);
    const el = containerRef.current;
    if (!b || !el) return;
    const width = el.clientWidth || 800;
    const height = el.clientHeight || 600;
    try {
      const vp = new WebMercatorViewport({ width, height });
      const { longitude, latitude, zoom } = vp.fitBounds(
        [
          [b[0], b[1]],
          [b[2], b[3]],
        ],
        { padding: 60 },
      );
      setViewState((v) => ({ ...v, longitude, latitude, zoom }));
      fitted.current = true;
    } catch {
      /* keep default view if the bbox is degenerate */
    }
  }, [trails]);

  const trailLayer = useMemo(
    () =>
      trails
        ? new GeoJsonLayer({
            id: "trails",
            data: trails,
            stroked: true,
            filled: false,
            pickable: false,
            getLineColor: [...TRAIL_COLOR, 180],
            getLineWidth: 1,
            lineWidthUnits: "pixels",
            lineWidthMinPixels: 1,
          })
        : null,
    [trails],
  );

  const candidateLayers = useMemo(() => {
    // Draw the active candidate last so it sits on top of the others.
    const order = candidates.map((_, i) => i);
    order.sort((a, b) => (a === activeIdx ? 1 : 0) - (b === activeIdx ? 1 : 0));
    return order.map((i) => {
      const isActive = activeIdx === i;
      const dimmed = activeIdx !== null && !isActive;
      const [r, g, b] = candidateColor(i);
      return new GeoJsonLayer({
        id: `cand-${i}`,
        data: candidates[i].geojson,
        pickable: true,
        stroked: true,
        filled: false,
        getLineColor: [r, g, b, dimmed ? 90 : 255],
        getLineWidth: isActive ? 6 : 4,
        lineWidthUnits: "pixels",
        lineWidthMinPixels: 2,
        capRounded: true,
        jointRounded: true,
        updateTriggers: {
          getLineColor: [activeIdx],
          getLineWidth: [activeIdx],
        },
      });
    });
  }, [candidates, activeIdx]);

  const startLayer = useMemo(
    () =>
      new ScatterplotLayer<LngLat>({
        id: "start",
        data: startSnapped ? [startSnapped] : [],
        getPosition: (d) => d,
        getRadius: 7,
        radiusUnits: "pixels",
        radiusMinPixels: 5,
        getFillColor: [187, 90, 51],
        getLineColor: [255, 255, 255],
        getLineWidth: 2,
        lineWidthUnits: "pixels",
        stroked: true,
        pickable: false,
      }),
    [startSnapped],
  );

  const layers = [trailLayer, ...candidateLayers, startLayer];

  const handleClick = (info: PickingInfo) => {
    const id = info.layer?.id;
    if (id && id.startsWith("cand-")) {
      onSelectCandidate(Number(id.slice(5)));
    } else if (info.coordinate) {
      onPickStart([info.coordinate[0], info.coordinate[1]]);
    }
  };

  const handleHover = (info: PickingInfo) => {
    const id = info.layer?.id;
    onHoverCandidate(id && id.startsWith("cand-") ? Number(id.slice(5)) : null);
  };

  return (
    <div className="map-canvas" ref={containerRef}>
      <DeckGL
        layers={layers}
        viewState={viewState}
        controller={true}
        onViewStateChange={(e) =>
          setViewState((e as { viewState: ViewState }).viewState)
        }
        onClick={handleClick}
        onHover={handleHover}
        getCursor={({ isHovering }) => (isHovering ? "pointer" : "crosshair")}
      >
        <Map mapStyle={MAP_STYLE} attributionControl={{ compact: true }} />
      </DeckGL>
      {!startSnapped && (
        <div className="map-hint">在地图上点击任意位置选择起点</div>
      )}
    </div>
  );
}

/** [minLng, minLat, maxLng, maxLat] over all geometry coordinates, or null. */
function featureCollectionBounds(
  fc: GeoJSON.FeatureCollection,
): [number, number, number, number] | null {
  let minX = Infinity;
  let minY = Infinity;
  let maxX = -Infinity;
  let maxY = -Infinity;
  const visit = (coords: unknown): void => {
    if (typeof (coords as number[])[0] === "number") {
      const [x, y] = coords as number[];
      if (x < minX) minX = x;
      if (y < minY) minY = y;
      if (x > maxX) maxX = x;
      if (y > maxY) maxY = y;
    } else {
      for (const c of coords as unknown[]) visit(c);
    }
  };
  for (const f of fc.features) {
    const g = f.geometry;
    if (g && "coordinates" in g) visit(g.coordinates);
  }
  return minX === Infinity ? null : [minX, minY, maxX, maxY];
}
