import { ReactNode } from 'react';
import { Link, NavLink } from 'react-router-dom';
import './Layout.css';

interface LayoutProps {
  children: ReactNode;
}

const Layout = ({ children }: LayoutProps) => {
  return (
    <div className="app-shell">
      <header className="app-header">
        <div className="header-content">
          <Link to="/" className="brand">
            <span className="brand-mark" aria-hidden>
              DS
            </span>
            <span className="brand-name">DualSPHysics Control Center</span>
          </Link>
          <nav className="primary-nav">
            <NavLink to="/" className={({ isActive }) => (isActive ? 'active' : '')} end>
              Runs
            </NavLink>
          </nav>
        </div>
      </header>
      <main className="app-main">{children}</main>
    </div>
  );
};

export default Layout;
