export default function TopBar() {
  return (
    <header className="fixed top-0 left-[240px] right-0 h-16 z-30 bg-surface-main border-b border-border-subtle flex items-center justify-end px-6">
      {/* Right controls */}
      <div className="flex items-center gap-4">
        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center cursor-pointer border border-primary/30">
          <span className="text-primary text-xs font-semibold">U</span>
        </div>
      </div>
    </header>
  );
}
