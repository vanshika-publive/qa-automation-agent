import { NavLink } from 'react-router-dom';
import { FolderOpen, PlayCircle, Network } from 'lucide-react';

const navItems = [
  { to: '/', icon: FolderOpen, label: 'Collections', end: true },
  { to: '/executions', icon: PlayCircle, label: 'Executions', end: false },
  { to: '/environments', icon: Network, label: 'Environments', end: false },
];

export default function Sidebar() {
  return (
    <aside className="flex flex-col h-screen fixed left-0 top-0 w-[240px] z-40 bg-surface-sidebar">
      {/* Logo */}
      <div className="p-6">
        <div className="flex flex-col gap-1.5 mb-8">
          <img
            src="https://img-cdn.publive.online/publive/logo/publive-white-full-logo.svg"
            alt="Publive"
            className="h-7 w-auto object-contain object-left"
          />
          <p className="text-secondary-fixed-dim text-[10px] uppercase tracking-widest font-semibold opacity-60 pl-0.5">
            Test Manager
          </p>
        </div>

        {/* Nav */}
        <nav className="space-y-1">
          {navItems.map(({ to, icon: Icon, label, end }) => (
            <NavLink
              key={to}
              to={to}
              end={end}
              className={({ isActive }) =>
                isActive
                  ? 'flex items-center gap-3 px-4 py-3 text-white border-l-4 border-primary bg-on-secondary-fixed-variant/10 transition-all duration-200'
                  : 'flex items-center gap-3 px-4 py-3 text-secondary-fixed-dim hover:text-white hover:bg-on-secondary-fixed-variant/5 transition-colors'
              }
            >
              <Icon size={22} />
              <span className="font-body-medium text-body-medium">{label}</span>
            </NavLink>
          ))}
        </nav>
      </div>

      {/* User section */}
      <div className="mt-auto p-6">
        <div className="pt-4 border-t border-white/10 flex items-center gap-3 px-4">
          <div className="w-8 h-8 rounded-full bg-primary/40 flex items-center justify-center flex-shrink-0 border border-white/20">
            <span className="text-white text-xs font-semibold">U</span>
          </div>
          <div className="overflow-hidden">
            <p className="text-white text-xs font-semibold truncate">User</p>
            <p className="text-secondary-fixed-dim text-[10px] truncate">user@thepublive.com</p>
          </div>
        </div>
      </div>
    </aside>
  );
}
