// Banner: floating notice over the map. `warn` carries the backend's
// reachability `note` (e.g. "该片区最多约 2.3km"); `error` carries a failure.

type Props = {
  kind: "warn" | "error";
  text: string;
};

export function Banner({ kind, text }: Props) {
  return (
    <div className={`banner banner--${kind}`} role="status">
      <span className="banner__icon">{kind === "error" ? "!" : "i"}</span>
      <span>{text}</span>
    </div>
  );
}
