import React from 'react';
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom';
import LoginPage from './pages/LoginPage';
import Layout from './components/Layout';
import DashboardPage from './pages/DashboardPage';
import ScrapersPage from './pages/ScrapersPage';
import ProductsPage from './pages/ProductsPage';
import PricesPage from './pages/PricesPage';
import StoresPage from './pages/StoresPage';

function RequireAuth({ children }: { children: React.ReactNode }) {
  const token = localStorage.getItem('admin_token');
  return token ? <>{children}</> : <Navigate to="/login" replace />;
}

export default function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route
          path="/"
          element={
            <RequireAuth>
              <Layout />
            </RequireAuth>
          }
        >
          <Route index element={<Navigate to="/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="scrapers" element={<ScrapersPage />} />
          <Route path="products" element={<ProductsPage />} />
          <Route path="prices" element={<PricesPage />} />
          <Route path="stores" element={<StoresPage />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}
