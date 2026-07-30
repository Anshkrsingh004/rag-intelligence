/** Fixed, non-interactive flowing-gradient backdrop behind all content. */
export function Aurora() {
  return (
    <div className="aurora" aria-hidden>
      <div className="aurora-blob aurora-1" />
      <div className="aurora-blob aurora-2" />
      <div className="aurora-blob aurora-3" />
      <div className="aurora-grid" />
    </div>
  );
}
