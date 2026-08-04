import React from 'react';
import { Outlet, NavLink, useNavigate } from 'react-router-dom';

const NAV = [
  { to: '/dashboard', label: '📊 Dashboard' },
  { to: '/scrapers', label: '🤖 Scrapers' },
  { to: '/products', label: '📦 Produits' },
  { to: '/prices', label: '💰 Prix' },
  { to: '/stores', label: '🏪 Magasins' },
];

export default function Layout() {
  const navigate = useNavigate();

  const handleLogout = () => {
    localStorage.removeItem('admin_token');
    navigate('/login');
  };

  return (
    <div className="flex h-screen bg-gray-50">
      {/* Sidebar */}
      <aside className="w-60 bg-white border-r border-gray-200 flex flex-col">
        <div className="p-6 border-b border-gray-100">
          <h1 className="text-lg font-black text-green-700">PrixMaroc</h1>
          <p className="text-xs text-gray-400 mt-1">Panel Administration</p>
        </div>
        <nav className="flex-1 p-4 space-y-1">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              className={({ isActive }) =>
                `block px-4 py-2.5 rounded-lg text-sm font-semibold transition-colors ${
                  isActive
                    ? 'bg-green-50 text-green-700'
                    : 'text-gray-600 hover:bg-gray-50 hover:text-gray-900'
                }`
              }
            >
              {item.label}
            </NavLink>
          ))}
        </nav>
        <div className="p-4 border-t border-gray-100">
          <button
            onClick={handleLogout}
            className="w-full px-4 py-2 text-sm font-semibold text-red-600 hover:bg-red-50 rounded-lg transition-colors"
          >
            🚪 Déconnexion
          </button>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex-1 overflow-auto">
        <Outlet />
      </main>
    </div>
  );
}
