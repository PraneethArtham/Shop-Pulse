import { Link } from 'react-router-dom';
import styles from './Breadcrumb.module.css';

// Accepts either `crumbs` or `items` prop for backwards compatibility
export default function Breadcrumb({ crumbs, items }) {
  const data = crumbs || items || [];
  return (
    <nav className={styles.breadcrumb} aria-label="Breadcrumb">
      {data.map((crumb, i) => (
        <span key={i} className={styles.item}>
          {i < data.length - 1 ? (
            <>
              <Link to={crumb.to} className={styles.link}>{crumb.label}</Link>
              <span className={styles.sep}>›</span>
            </>
          ) : (
            <span className={styles.current}>{crumb.label}</span>
          )}
        </span>
      ))}
    </nav>
  );
}
