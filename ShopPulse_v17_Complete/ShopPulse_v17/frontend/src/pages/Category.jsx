import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import { fetchProductsByCategory } from '../utils/api';
import { CATEGORY_ICONS } from '../utils/helpers';
import ProductCard from '../components/ProductCard';
import Breadcrumb from '../components/Breadcrumb';
import Loader, { CardSkeleton } from '../components/Loader';
import EmptyState from '../components/EmptyState';
import styles from './Category.module.css';

const SORT_OPTIONS = [
  { value: '',           label: 'Recommended' },
  { value: 'price_asc',  label: 'Price ↑' },
  { value: 'price_desc', label: 'Price ↓' },
  { value: 'name_asc',   label: 'Name A–Z' },
  { value: 'name_desc',  label: 'Name Z–A' },
];

export default function Category() {
  const { categoryName } = useParams();
  const decoded = decodeURIComponent(categoryName);

  const [products, setProducts] = useState([]);
  const [loading, setLoading]   = useState(true);
  const [error, setError]       = useState(null);
  const [sort, setSort]         = useState('');
  const [page, setPage]         = useState(1);
  const LIMIT = 20;

  useEffect(() => {
    setLoading(true);
    setError(null);
    fetchProductsByCategory(decoded, page, LIMIT, sort || null)
      .then((d) => setProducts(d.products || []))
      .catch((e) => setError(e.response?.data?.detail || 'Failed to load products'))
      .finally(() => setLoading(false));
  }, [decoded, sort, page]);

  const handleSort = (val) => { setSort(val); setPage(1); };

  return (
    <div className={styles.page}>
      <Breadcrumb crumbs={[
        { to: '/', label: 'Home' },
        { label: decoded },
      ]} />

      <div className={styles.header}>
        <h1 className={styles.title}>
          {CATEGORY_ICONS[decoded] || '🛒'} {decoded}
        </h1>
        {!loading && (
          <span className={styles.count}>{products.length} products</span>
        )}
      </div>

      {/* Sort bar */}
      <div className={styles.toolbar}>
        <span className={styles.toolbarLabel}>Sort by:</span>
        {SORT_OPTIONS.map((opt) => (
          <button
            key={opt.value}
            className={`${styles.sortChip} ${sort === opt.value ? styles.active : ''}`}
            onClick={() => handleSort(opt.value)}
          >
            {opt.label}
          </button>
        ))}
      </div>

      {/* Content */}
      {error ? (
        <EmptyState icon="⚠️" title="Failed to load" subtitle={error} />
      ) : loading ? (
        <div className={styles.grid}>
          {Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)}
        </div>
      ) : products.length === 0 ? (
        <EmptyState icon="📦" title="No products found" subtitle="This category has no products yet." />
      ) : (
        <>
          <div className={`${styles.grid} stagger`}>
            {products.map((p) => <ProductCard key={p.master_product_id} product={p} />)}
          </div>

          {/* Pagination */}
          <div className={styles.pagination}>
            <button
              className={styles.pageBtn}
              disabled={page === 1}
              onClick={() => setPage((p) => p - 1)}
            >
              ← Prev
            </button>
            <span className={styles.pageInfo}>Page {page}</span>
            <button
              className={styles.pageBtn}
              disabled={products.length < LIMIT}
              onClick={() => setPage((p) => p + 1)}
            >
              Next →
            </button>
          </div>
        </>
      )}
    </div>
  );
}
