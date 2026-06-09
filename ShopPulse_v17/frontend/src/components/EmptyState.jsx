import styles from './EmptyState.module.css';

export default function EmptyState({ icon = '📦', title, subtitle, action }) {
  return (
    <div className={styles.wrap}>
      <div className={styles.icon}>{icon}</div>
      <h3 className={styles.title}>{title}</h3>
      {subtitle && <p className={styles.subtitle}>{subtitle}</p>}
      {action && <div className={styles.action}>{action}</div>}
    </div>
  );
}
