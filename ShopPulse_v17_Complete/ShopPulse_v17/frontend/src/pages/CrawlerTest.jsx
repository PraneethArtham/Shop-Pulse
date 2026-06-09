import { useState } from 'react';
import { testCrawlers } from '../utils/api';
import styles from './CrawlerTest.module.css';

const PLATFORMS = ['all', 'amazon', 'croma', 'reliance', 'bigbasket'];

const STATUS_ICON = { ok: '✅', empty: '⚠️', error: '❌', pending: '⏳' };
const STATUS_LABEL = { ok: 'Working', empty: 'No results', error: 'Error', pending: 'Testing…' };

export default function CrawlerTest() {
  const [query, setQuery]       = useState('trimmer');
  const [platform, setPlatform] = useState('all');
  const [loading, setLoading]   = useState(false);
  const [report, setReport]     = useState(null);
  const [error, setError]       = useState(null);

  const run = async () => {
    if (!query.trim()) return;
    setLoading(true);
    setError(null);
    setReport(null);
    try {
      const data = await testCrawlers(query.trim(), platform);
      setReport(data);
    } catch (e) {
      setError(e.response?.data?.detail || e.message || 'Request failed');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>🔬 Crawler Diagnostics</h1>
        <p className={styles.subtitle}>
          Test each platform crawler directly — no DB writes. See exactly what gets scraped.
        </p>
      </div>

      {/* Controls */}
      <div className={styles.controls}>
        <div className={styles.inputGroup}>
          <label className={styles.label}>Search Query</label>
          <input
            className={styles.input}
            value={query}
            onChange={e => setQuery(e.target.value)}
            onKeyDown={e => e.key === 'Enter' && run()}
            placeholder="e.g. trimmer, laptop, headphone"
          />
        </div>
        <div className={styles.inputGroup}>
          <label className={styles.label}>Platform</label>
          <div className={styles.platformBtns}>
            {PLATFORMS.map(p => (
              <button
                key={p}
                className={`${styles.platformBtn} ${platform === p ? styles.platformBtnActive : ''}`}
                onClick={() => setPlatform(p)}
              >
                {p === 'all' ? '🌐 All' : p === 'amazon' ? '🛒 Amazon' : p === 'croma' ? '🏪 Croma' : p === 'reliance' ? '⚡ Reliance' : '🛍️ BigBasket'}
              </button>
            ))}
          </div>
        </div>
        <button className={styles.runBtn} onClick={run} disabled={loading || !query.trim()}>
          {loading ? <><span className={styles.spinner} /> Running…</> : '▶ Run Test'}
        </button>
      </div>

      {/* Error */}
      {error && (
        <div className={styles.errorBox}>❌ {error}</div>
      )}

      {/* Loading */}
      {loading && (
        <div className={styles.loadingBox}>
          <span className={styles.spinner} />
          <span>Crawling <strong>{query}</strong> on <strong>{platform}</strong>… this takes 10–30 seconds</span>
        </div>
      )}

      {/* Results */}
      {report && !loading && (
        <div className={styles.report}>

          {/* Summary bar */}
          <div className={styles.summaryBar}>
            <div className={styles.summaryItem}>
              <span className={styles.summaryNum}>{report.summary.total_products}</span>
              <span className={styles.summaryLabel}>Total Products</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={`${styles.summaryNum} ${styles.green}`}>{report.summary.working.length}</span>
              <span className={styles.summaryLabel}>✅ Working</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={`${styles.summaryNum} ${styles.yellow}`}>{report.summary.empty.length}</span>
              <span className={styles.summaryLabel}>⚠️ Empty</span>
            </div>
            <div className={styles.summaryItem}>
              <span className={`${styles.summaryNum} ${styles.red}`}>{report.summary.errors.length}</span>
              <span className={styles.summaryLabel}>❌ Errors</span>
            </div>
          </div>

          {/* Per-platform panels */}
          {Object.entries(report.platforms).map(([name, data]) => (
            <div key={name} className={`${styles.platformPanel} ${styles['panel_' + data.status]}`}>
              <div className={styles.panelHeader}>
                <div className={styles.panelLeft}>
                  <span className={styles.panelIcon}>{STATUS_ICON[data.status]}</span>
                  <div>
                    <div className={styles.panelName}>{name}</div>
                    <div className={styles.panelMeta}>
                      <span className={`${styles.statusChip} ${styles['chip_' + data.status]}`}>
                        {STATUS_LABEL[data.status]}
                      </span>
                      <span className={styles.metaItem}>⏱ {data.time_sec}s</span>
                      <span className={styles.metaItem}>📦 {data.count} products</span>
                    </div>
                  </div>
                </div>
              </div>

              {/* Error message */}
              {data.error && (
                <div className={styles.errorMsg}>
                  <strong>Error:</strong> {data.error}
                </div>
              )}

              {/* Product table */}
              {data.products.length > 0 && (
                <div className={styles.tableWrap}>
                  <table className={styles.table}>
                    <thead>
                      <tr>
                        <th>#</th>
                        <th>Product Name</th>
                        <th>Price</th>
                        <th>Rating</th>
                        <th>Link</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.products.map((p, i) => (
                        <tr key={i}>
                          <td className={styles.numCell}>{i + 1}</td>
                          <td className={styles.nameCell}>{p.product_name}</td>
                          <td className={styles.priceCell}>
                            {p.price ? `₹${p.price.toLocaleString('en-IN')}` : <span className={styles.na}>—</span>}
                          </td>
                          <td className={styles.ratingCell}>
                            {p.rating ? `★ ${p.rating}` : <span className={styles.na}>—</span>}
                          </td>
                          <td className={styles.linkCell}>
                            {p.product_url
                              ? <a href={p.product_url} target="_blank" rel="noreferrer" className={styles.link}>↗ View</a>
                              : <span className={styles.na}>—</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}

              {data.status === 'empty' && !data.error && (
                <div className={styles.emptyMsg}>
                  Crawler ran successfully but found 0 products for "<strong>{report.query}</strong>" on {name}.
                  This usually means the query doesn't match a known category — try "trimmer", "laptop", or "headphone".
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
