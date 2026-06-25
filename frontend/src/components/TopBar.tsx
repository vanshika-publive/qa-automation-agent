import { Search } from 'lucide-react';

export default function TopBar() {
  return (
    <header className="fixed top-0 left-[240px] right-0 h-16 z-30 bg-surface-main border-b border-border-subtle flex items-center justify-between px-6">
      {/* Search */}
      <div className="flex items-center gap-4 flex-1">
        <div className="relative max-w-md w-full">
          <Search size={20} className="absolute left-3 top-1/2 -translate-y-1/2 text-text-secondary" />
          <input
            type="text"
            placeholder="Search collections or tests..."
            className="w-full bg-surface-muted border-none rounded-xl pl-10 pr-4 py-2 text-sm text-text-primary placeholder:text-text-secondary focus:outline-none focus:ring-2 focus:ring-primary/20 transition-all"
          />
        </div>
      </div>

      {/* Right controls */}
      <div className="flex items-center gap-4">
        <div className="w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center cursor-pointer border border-primary/30">
          <span className="text-primary text-xs font-semibold">U</span>
        </div>
      </div>
    </header>
  );
}
