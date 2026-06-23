import { useState } from 'react';
import { NavLink, useLocation, useSearchParams } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { api } from '../api/client';
import { ApiResponse, Collection } from '../types';

const navItems = [
  { to: '/', icon: 'folder_open', label: 'Collections', end: true },
  { to: '/executions', icon: 'play_circle', label: 'Executions', end: false },
  { to: '/environments', icon: 'settings_ethernet', label: 'Environments', end: false },
];

export default function Sidebar() {
  const location = useLocation();
  const [searchParams, setSearchParams] = useSearchParams();
  const [treeExpanded, setTreeExpanded] = useState(true);
  const selectedColId = searchParams.get('col');
  const isCollectionsPage = location.pathname === '/';

  const { data: collectionsData } = useQuery({
    queryKey: ['collections'],
    queryFn: () => api.get<ApiResponse<Collection[]>>('/collections'),
    enabled: isCollectionsPage,
  });
  const collections = collectionsData?.data ?? [];

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
          {navItems.map(({ to, icon, label, end }) => (
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
              <span className="material-symbols-outlined" style={{ fontSize: 22 }}>{icon}</span>
              <span className="font-body-medium text-body-medium">{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Collections tree — only on the Collections page */}
        {isCollectionsPage && collections.length > 0 && (
          <div className="mt-4 pt-4 border-t border-white/10">
            <button
              onClick={() => setTreeExpanded((v) => !v)}
              className="flex items-center justify-between w-full px-2 py-1.5 text-secondary-fixed-dim hover:text-white transition-colors"
            >
              <span className="text-[10px] font-semibold uppercase tracking-widest opacity-70">Collections</span>
              <span
                className="material-symbols-outlined transition-transform duration-200"
                style={{ fontSize: 14, transform: treeExpanded ? 'rotate(180deg)' : 'rotate(0deg)' }}
              >
                expand_more
              </span>
            </button>

            {treeExpanded && (
              <div className="mt-1 space-y-0.5">
                {collections.map((col) => (
                  <button
                    key={col.id}
                    onClick={() => setSearchParams({ col: col.id })}
                    className={[
                      'flex items-center gap-2 w-full px-3 py-1.5 text-sm transition-colors text-left',
                      selectedColId === col.id
                        ? 'text-white bg-white/10'
                        : 'text-secondary-fixed-dim hover:text-white hover:bg-white/5',
                    ].join(' ')}
                  >
                    <span className="material-symbols-outlined flex-shrink-0 opacity-60" style={{ fontSize: 14 }}>
                      folder
                    </span>
                    <span className="truncate flex-1 text-xs">{col.name}</span>
                    <span className="text-[10px] opacity-50 flex-shrink-0">{col.testCount}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
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
