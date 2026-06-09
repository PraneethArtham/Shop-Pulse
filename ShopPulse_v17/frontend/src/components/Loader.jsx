import styles from './Loader.module.css';

export default function Loader({ message = 'Loading...' }) {
  return (
    <div className={styles.wrap}>
      <div className={styles.spinner} />
      {message && <p className={styles.message}>{message}</p>}
    </div>
  );
}

export function CardSkeleton() {
  return (
    <div className={styles.skeletonCard}>
      <div className={`${styles.skeletonImg} skeleton`} />
      <div className={styles.skeletonBody}>
        <div className={`${styles.skeletonLine} ${styles.short} skeleton`} />
        <div className={`${styles.skeletonLine} skeleton`} />
        <div className={`${styles.skeletonLine} ${styles.medium} skeleton`} />
      </div>
    </div>
  );
}
