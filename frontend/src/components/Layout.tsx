import { Outlet } from 'react-router-dom';
import Sidebar from './Sidebar';
import TopBar from './TopBar';

export default function Layout() {
  return (
    <div className="min-h-screen bg-background">
      <Sidebar />
      <TopBar />
      <main className="ml-[240px] pt-16 min-h-screen bg-background">
        <Outlet />
      </main>
    </div>
  );
}
