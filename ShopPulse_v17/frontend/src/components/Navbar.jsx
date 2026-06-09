import { useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router-dom';
import styles from './Navbar.module.css';

export default function Navbar() {
  const navigate = useNavigate();
  const location = useLocation();
  const [q, setQ]           = useState('');
  const [menuOpen, setMenu] = useState(false);

  const handleSearch = (e) => {
    e.preventDefault();
    if (q.trim()) { navigate(`/search?q=${encodeURIComponent(q.trim())}`); setQ(''); setMenu(false); }
  };

  const active = (p) => location.pathname === p ? styles.active : '';
  const startsWith = (p) => location.pathname.startsWith(p) ? styles.active : '';

  return (
    <header className={styles.header}>
      <div className={styles.inner}>
        <Link to="/" className={styles.logo}>
          <span className={styles.logoIcon}>🛍️</span>
          <span className={styles.logoText}>ShopPulse</span>
        </Link>

        <form className={styles.searchForm} onSubmit={handleSearch}>
          <span className={styles.searchIcon}>🔍</span>
          <input
            className={styles.searchInput}
            value={q}
            onChange={e => setQ(e.target.value)}
            placeholder='Search products… try "trimmer under ₹500"'
          />
          {q && <button type="button" className={styles.clearBtn} onClick={() => setQ('')}>✕</button>}
          <button type="submit" className={styles.searchBtn}>Search</button>
        </form>

        <nav className={styles.nav}>
          <Link to="/"           className={`${styles.link} ${active('/')}`}>Home</Link>
          <Link to="/search"     className={`${styles.link} ${active('/search')}`}>Browse</Link>
          <Link to="/stores"     className={`${styles.link} ${startsWith('/store')}`}>🏪 Stores</Link>
          <Link to="/store/register" className={`${styles.link} ${styles.sellerLink} ${startsWith('/store/register')}`}>
            For Sellers
          </Link>
          <Link to="/crawl-test" className={`${styles.link} ${styles.devLink} ${active('/crawl-test')}`}>Dev</Link>
        </nav>
      </div>
    </header>
  );
}
