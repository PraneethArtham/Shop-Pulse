import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchStores } from '../utils/api';
import styles from './StoresList.module.css';

export default function StoresList() {
  const navigate   = useNavigate();
  const [stores,   setStores]   = useState([]);
  const [loading,  setLoading]  = useState(true);
  const [error,    setError]    = useState(null);
  const [search,   setSearch]   = useState('');
  const [query,    setQuery]    = useState('');

  useEffect(() => {
    setLoading(true); setError(null);
    fetchStores(query)
      .then(d => setStores(d.stores || []))
      .catch(() => setError('Failed to load stores'))
      .finally(() => setLoading(false));
  }, [query]);

  const handleSearch = (e) => {
    e.preventDefault();
    setQuery(search.trim());
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>🏪 Local Stores</h1>
        <p className={styles.sub}>Find local stores near you and compare their prices with online platforms</p>
      </div>

      {/* Search bar */}
      <form className={styles.searchForm} onSubmit={handleSearch}>
        <span className={styles.searchIcon}>📍</span>
        <input
          className={styles.searchInput}
          placeholder="Search by location — e.g. Banjara Hills, Mumbai"
          value={search}
          onChange={e => setSearch(e.target.value)}
        />
        {search && (
          <button type="button" className={styles.clearBtn}
            onClick={() => { setSearch(''); setQuery(''); }}>✕</button>
        )}
        <button type="submit" className={styles.searchBtn}>Search</button>
      </form>

      {query && (
        <div className={styles.resultMeta}>
          Showing stores in <strong>"{query}"</strong>
          <button className={styles.clearSearch} onClick={() => { setSearch(''); setQuery(''); }}>
            Clear ✕
          </button>
        </div>
      )}

      {/* Register CTA */}
      <div className={styles.ctaBar}>
        <span>🏬 Own a local store?</span>
        <button className={styles.ctaBtn} onClick={() => navigate('/store/register')}>
          Register your store →
        </button>
      </div>

      {/* Stores grid */}
      {loading ? (
        <div className={styles.grid}>
          {Array.from({ length: 6 }).map((_, i) => (
            <div key={i} className={`${styles.card} ${styles.skeleton}`} style={{ height: 160 }} />
          ))}
        </div>
      ) : error ? (
        <div className={styles.empty}>⚠️ {error}</div>
      ) : stores.length === 0 ? (
        <div className={styles.empty}>
          <span>🏪</span>
          <h3>No stores found{query ? ` in "${query}"` : ''}</h3>
          <p>Be the first to register a store in this area!</p>
          <button className={styles.registerBtn} onClick={() => navigate('/store/register')}>
            Register your store
          </button>
        </div>
      ) : (
        <div className={styles.grid}>
          {stores.map(store => (
            <div
              key={store.store_id}
              className={styles.card}
              onClick={() => navigate(`/store/dashboard?id=${store.store_id}`)}
              role="button" tabIndex={0}
              onKeyDown={e => e.key === 'Enter' && navigate(`/store/dashboard?id=${store.store_id}`)}
            >
              <div className={styles.cardTop}>
                <div className={styles.cardIcon}>🏪</div>
                <div className={styles.cardInfo}>
                  <div className={styles.cardName}>{store.store_name}</div>
                  <div className={styles.cardLoc}>📍 {store.location}</div>
                </div>
              </div>

              <div className={styles.cardMeta}>
                {store.phone && (
                  <span className={styles.metaChip}>📞 {store.phone}</span>
                )}
                {store.store_rating && (
                  <span className={styles.metaChip}>⭐ {store.store_rating}</span>
                )}
                <span className={styles.metaChip}>
                  📦 {store.product_count ?? 0} products
                </span>
              </div>

              <div className={styles.cardFooter}>
                <span className={styles.viewBtn}>View store →</span>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
