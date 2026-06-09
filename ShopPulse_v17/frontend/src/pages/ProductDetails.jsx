import { useEffect, useState, useMemo } from 'react';
import { useParams } from 'react-router-dom';
import { fetchProductDetails, fetchPriceHistory, fetchPricePrediction } from '../utils/api';
import { renderStars } from '../utils/helpers';
import Breadcrumb from '../components/Breadcrumb';
import Loader from '../components/Loader';
import EmptyState from '../components/EmptyState';
import styles from './ProductDetails.module.css';

const PLATFORM_META = {
  'Amazon':           { color: '#FF9900', bg: 'rgba(255,153,0,0.12)',  icon: '🛒' },
  'Croma':            { color: '#0066CC', bg: 'rgba(0,102,204,0.12)', icon: '🏪' },
  'Reliance Digital': { color: '#0033A0', bg: 'rgba(0,51,160,0.12)',  icon: '⚡' },
  'BigBasket':        { color: '#84C225', bg: 'rgba(132,194,37,0.12)', icon: '🛍️' },
};
const getPM = (n) => PLATFORM_META[n] || { color: '#888', bg: 'rgba(128,128,128,0.1)', icon: '🏬' };

// ── Verification Score Section ─────────────────────────────
function VerificationSection({ listings }) {
  if (!listings?.length) return null;

  // Aggregate verification across all platform listings
  const scores = listings.map(l => l.verification_score).filter(Boolean);
  if (!scores.length) return null;

  const avgScore = Math.round(scores.reduce((s, v) => s + v.score, 0) / scores.length);
  const allFlags = [...new Set(scores.flatMap(v => v.flags || []))];
  const grade    = avgScore >= 80 ? 'A' : avgScore >= 60 ? 'B' : avgScore >= 40 ? 'C' : 'D';
  const gradeColor = { A: '#10b981', B: '#6366f1', C: '#f59e0b', D: '#ef4444' }[grade];

  // Aggregate breakdown across all platforms
  const breakdown = scores.reduce((acc, v) => {
    const b = v.breakdown || {};
    acc.review_credibility += b.review_credibility || 0;
    acc.rating_consistency += b.rating_consistency || 0;
    acc.seller_reputation  += b.seller_reputation  || 0;
    acc.price_signal       += b.price_signal        || 0;
    return acc;
  }, { review_credibility: 0, rating_consistency: 0, seller_reputation: 0, price_signal: 0 });

  const n = scores.length;
  const avgBreakdown = {
    'Review Credibility': { score: Math.round(breakdown.review_credibility / n), max: 40, icon: '💬' },
    'Rating Consistency': { score: Math.round(breakdown.rating_consistency / n), max: 25, icon: '⭐' },
    'Seller Reputation':  { score: Math.round(breakdown.seller_reputation / n),  max: 20, icon: '🏪' },
    'Price Signal':       { score: Math.round(breakdown.price_signal / n),        max: 15, icon: '💰' },
  };

  return (
    <section className={styles.section}>
      <h2 className={styles.sTitle}>
        🛡️ AI Verification Score
        <span className={styles.sCnt}>Trust analysis</span>
      </h2>
      <p className={styles.sSub}>
        ML-computed trust score based on review credibility, rating consistency, seller reputation and price signals
      </p>

      <div className={styles.vsPanel}>
        {/* Grade + score */}
        <div className={styles.vsLeft}>
          <div className={styles.vsGrade} style={{ color: gradeColor, borderColor: gradeColor + '60', background: gradeColor + '12' }}>
            {grade}
          </div>
          <div>
            <div className={styles.vsScore} style={{ color: gradeColor }}>{avgScore}<span>/100</span></div>
            <div className={styles.vsLabel}>
              {avgScore >= 75 ? 'Highly Trustworthy' : avgScore >= 50 ? 'Generally Reliable' : avgScore >= 35 ? 'Mixed Signals' : 'Low Confidence'}
            </div>
          </div>
        </div>

        {/* Overall bar */}
        <div className={styles.vsBarWrap}>
          <div className={styles.vsBarTrack}>
            <div className={styles.vsBarFill}
              style={{ width: `${avgScore}%`, background: gradeColor }} />
          </div>
          <div className={styles.vsBarLabels}>
            <span>0</span><span>25</span><span>50</span><span>75</span><span>100</span>
          </div>
        </div>
      </div>

      {/* Breakdown */}
      <div className={styles.vsBreakdown}>
        {Object.entries(avgBreakdown).map(([label, { score, max, icon }]) => (
          <div key={label} className={styles.vsItem}>
            <div className={styles.vsItemHeader}>
              <span>{icon} {label}</span>
              <span className={styles.vsItemScore}>{score}/{max}</span>
            </div>
            <div className={styles.vsItemBar}>
              <div className={styles.vsItemFill}
                style={{ width: `${(score / max) * 100}%`, background: gradeColor }} />
            </div>
          </div>
        ))}
      </div>

      {/* Per-platform scores */}
      {listings.length > 1 && (
        <div className={styles.vsPlatforms}>
          {listings.map((item, i) => {
            const vs   = item.verification_score;
            const meta = getPM(item.platform_name);
            if (!vs) return null;
            const g    = vs.grade;
            const gc   = { A: '#10b981', B: '#6366f1', C: '#f59e0b', D: '#ef4444' }[g];
            return (
              <div key={i} className={styles.vsPlatformRow}>
                <span style={{ color: meta.color }}>{meta.icon} {item.platform_name}</span>
                <div className={styles.vsPlatformBar}>
                  <div style={{ width: `${vs.score}%`, background: gc, height: '100%', borderRadius: 3 }} />
                </div>
                <span className={styles.vsPlatformScore} style={{ color: gc }}>
                  {g} · {vs.score}/100
                </span>
              </div>
            );
          })}
        </div>
      )}

      {/* Flags */}
      {allFlags.length > 0 && (
        <div className={styles.vsFlags}>
          {allFlags.map((f, i) => (
            <span key={i} className={styles.vsFlag}>⚠ {f}</span>
          ))}
        </div>
      )}
    </section>
  );
}

// ── Price Prediction Section ───────────────────────────────
function PredictionSection({ prediction }) {
  if (!prediction?.overall) return null;
  const { overall, platforms, total_data_points, method } = prediction;
  const adviceColor = { buy_now: '#10b981', wait: '#f59e0b', neutral: '#888' }[overall.best_time_to_buy] || '#888';
  const adviceIcon  = { buy_now: '✅', wait: '⏳', neutral: '➡️' }[overall.best_time_to_buy] || '➡️';
  const adviceLabel = { buy_now: 'Buy Now', wait: 'Wait for Better Price', neutral: 'Price Stable' }[overall.best_time_to_buy];

  return (
    <section className={styles.section}>
      <h2 className={styles.sTitle}>
        🔮 AI Price Prediction
        <span className={styles.sCnt}>7-day forecast</span>
      </h2>
      <p className={styles.sSub}>
        Numpy linear regression on {total_data_points} price data point{total_data_points !== 1 ? 's' : ''} · {method?.replace(/_/g,' ')}
      </p>

      {/* Overall verdict */}
      <div className={styles.predVerdict} style={{ borderColor: adviceColor + '50', background: adviceColor + '08' }}>
        <span className={styles.predVerdictIcon}>{adviceIcon}</span>
        <div>
          <div className={styles.predVerdictLabel} style={{ color: adviceColor }}>{adviceLabel}</div>
          <div className={styles.predVerdictReason}>{overall.reason}</div>
          {overall.seasonal_note && (
            <div className={styles.predSeasonal}>🗓️ {overall.seasonal_note}</div>
          )}
        </div>
        {overall.lowest_predicted && (
          <div className={styles.predBestPrice}>
            <div className={styles.predBestLabel}>Predicted best</div>
            <div className={styles.predBestVal} style={{ color: adviceColor }}>
              ₹{overall.lowest_predicted.toLocaleString('en-IN')}
            </div>
            <div className={styles.predBestPlat}>on {overall.platform}</div>
          </div>
        )}
      </div>

      {/* Per-platform breakdown */}
      {Object.entries(platforms || {}).length > 0 && (
        <div className={styles.predGrid}>
          {Object.entries(platforms).map(([plat, data]) => {
            const meta      = getPM(plat);
            const trendUp   = data.trend === 'up';
            const trendDown = data.trend === 'down';
            const trendColor = trendDown ? '#10b981' : trendUp ? '#ef4444' : '#888';
            const trendIcon  = trendDown ? '↓' : trendUp ? '↑' : '→';
            const recColor   = { buy_now: '#10b981', wait: '#f59e0b', neutral: '#888' }[data.recommendation];
            const recLabel   = { buy_now: '✅ Buy Now', wait: '⏳ Wait', neutral: '→ Neutral' }[data.recommendation];
            const pctAbs     = Math.abs(data.trend_pct);

            return (
              <div key={plat} className={styles.predCard}>
                <div className={styles.predCardHead}>
                  <span style={{ color: meta.color, fontWeight: 700 }}>{meta.icon} {plat}</span>
                  <span className={styles.predConf} data-conf={data.confidence}>
                    {data.confidence} confidence · R²={data.r2_score}
                  </span>
                </div>

                <div className={styles.predPriceRow}>
                  <div>
                    <div className={styles.predPriceLabel}>Current</div>
                    <div className={styles.predPriceCurrent}>₹{data.current?.toLocaleString('en-IN')}</div>
                  </div>
                  <div className={styles.predArrow} style={{ color: trendColor }}>
                    {trendIcon} {pctAbs > 0.1 ? `${pctAbs.toFixed(1)}%` : '—'}
                  </div>
                  <div>
                    <div className={styles.predPriceLabel}>In 7 days</div>
                    <div className={styles.predPrice7d} style={{ color: trendColor }}>
                      ₹{data.predicted_7d?.toLocaleString('en-IN')}
                    </div>
                  </div>
                </div>

                <div className={styles.predCardFoot}>
                  <span className={styles.predATL}>
                    ATL ₹{data.all_time_low?.toLocaleString('en-IN')}
                    {data.dist_from_atl_pct > 0 && <span> (+{data.dist_from_atl_pct}%)</span>}
                  </span>
                  <span style={{ color: recColor, fontWeight: 700, fontSize: 12 }}>{recLabel}</span>
                </div>

                <div className={styles.predDataPts}>
                  {data.data_points} data point{data.data_points !== 1 ? 's' : ''}
                  {data.seasonal_active && ' · 🛍️ sale season'}
                </div>
              </div>
            );
          })}
        </div>
      )}
    </section>
  );
}

// ── Price Sparkline ───────────────────────────────────────
function Sparkline({ points, color }) {
  if (!points || points.length < 2) return null;
  const prices = points.map(p => p.price).filter(Boolean);
  if (prices.length < 2) return null;
  const minP = Math.min(...prices), maxP = Math.max(...prices);
  const range = maxP - minP || 1;
  const W = 160, H = 40, n = prices.length;
  const coords = prices.map((p, i) =>
    `${(i / Math.max(n - 1, 1)) * W},${H - ((p - minP) / range) * H}`
  ).join(' ');
  const parts = coords.split(' ');
  const last  = parts[parts.length - 1].split(',');
  return (
    <svg viewBox={`0 0 ${W} ${H}`} className={styles.spark}>
      <polyline points={coords} fill="none" stroke={color} strokeWidth="1.8" />
      <circle cx={last[0]} cy={last[1]} r="3" fill={color} />
    </svg>
  );
}

// ── Deal badges ───────────────────────────────────────────
function DealBadges({ summary, price }) {
  if (!summary || !price) return null;
  const badges = [];
  if (summary.is_all_time_low)     badges.push(['🔥 All-Time Low', styles.badgeAtl]);
  if (summary.savings_pct >= 30)   badges.push([`💰 ${summary.savings_pct}% below peak`, styles.badgeSave]);
  else if (summary.savings_pct >= 10) badges.push([`✂️ ${summary.savings_pct}% off peak`, styles.badgeSave]);
  return badges.length > 0 ? (
    <div className={styles.badges}>
      {badges.map(([label, cls], i) => <span key={i} className={`${styles.badge} ${cls}`}>{label}</span>)}
    </div>
  ) : null;
}

// ── Platform row ──────────────────────────────────────────
function PlatformRow({ item, isBest, maxPrice }) {
  const meta    = getPM(item.platform_name);
  const savings = maxPrice && item.price && maxPrice > item.price ? Math.round(maxPrice - item.price) : 0;
  const vs      = item.verification_score;
  const vColor  = vs ? { A: '#10b981', B: '#6366f1', C: '#f59e0b', D: '#ef4444' }[vs.grade] : null;

  return (
    <a href={item.product_url || '#'} target="_blank" rel="noreferrer"
       className={`${styles.platformRow} ${isBest ? styles.bestRow : ''}`}>
      <div className={styles.rowLeft}>
        <span className={styles.pBadge} style={{ background: meta.bg, color: meta.color }}>
          {meta.icon} {item.platform_name}
        </span>
        {isBest && <span className={styles.bestTag}>LOWEST</span>}
        {vs && (
          <span className={styles.trustChip} style={{ color: vColor, borderColor: vColor + '40' }}>
            🛡️ {vs.grade} {vs.score}/100
          </span>
        )}
      </div>
      <div className={styles.rowRight}>
        {savings > 0 && <span className={styles.saveChip}>save ₹{savings.toLocaleString('en-IN')}</span>}
        <span className={styles.rowPrice} style={isBest ? { color: '#10b981' } : {}}>
          ₹{item.price?.toLocaleString('en-IN')}
        </span>
        <span className={styles.visitBtn} style={{ background: meta.color }}>Visit ↗</span>
      </div>
    </a>
  );
}

// ── Review card ───────────────────────────────────────────
function ReviewCard({ review }) {
  const rating = review.review_rating ?? 0;
  const text   = review.review_text ?? '';
  const date   = review.created_at ? new Date(review.created_at).toLocaleDateString('en-IN') : '';
  const sent   = review.sentiment_score ?? 0.5;
  return (
    <div className={styles.reviewCard}>
      <div className={styles.reviewTop}>
        <span className={styles.stars}>{renderStars(rating)}</span>
        <span>{sent >= 0.7 ? '😊' : sent >= 0.4 ? '😐' : '😞'}</span>
        {review.is_fake && <span className={styles.fakeBadge}>⚠ Suspicious</span>}
        {date && <span className={styles.revDate}>{date}</span>}
      </div>
      {text && <p className={styles.revText}>{text}</p>}
    </div>
  );
}

// ── Main ──────────────────────────────────────────────────
export default function ProductDetails() {
  const { id } = useParams();
  const [data,       setData]       = useState(null);
  const [history,    setHistory]    = useState(null);
  const [prediction, setPrediction] = useState(null);
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState(null);

  useEffect(() => {
    setLoading(true);
    Promise.all([
      fetchProductDetails(id),
      fetchPriceHistory(id).catch(() => null),
      fetchPricePrediction(id).catch(() => null),
    ])
      .then(([d, h, p]) => { setData(d); setHistory(h); setPrediction(p); })
      .catch(e => setError(e.message || 'Failed to load product'))
      .finally(() => setLoading(false));
  }, [id]);

  const listings = data?.platform_listings || [];
  const prices   = listings.map(p => p.price).filter(Boolean);
  const lowestP  = prices.length ? Math.min(...prices) : null;
  const highestP = prices.length ? Math.max(...prices) : null;
  const allRevs  = useMemo(() => listings.flatMap(p => p.reviews || []).slice(0, 8), [listings]);
  const summary  = history?.summary;
  const stats    = data?.stats;

  if (loading) return <div className={styles.page}><Loader /></div>;
  if (error || !data) return (
    <div className={styles.page}>
      <EmptyState icon="😕" title="Product not found" subtitle={error} />
    </div>
  );

  const product = data.product;

  return (
    <div className={styles.page}>
      <Breadcrumb items={[
        { label: 'Home', to: '/' },
        { label: product.category || 'Products', to: `/category/${product.category}` },
        { label: product.product_name },
      ]} />

      {/* ── Hero ── */}
      <div className={styles.hero}>
        <div className={styles.heroImg}>
          {listings.find(p => p.image_url)?.image_url
            ? <img src={listings.find(p => p.image_url).image_url} alt={product.product_name}
                   onError={e => e.target.style.display = 'none'} />
            : <div className={styles.imgFallback}>📦</div>
          }
        </div>
        <div className={styles.heroInfo}>
          <div className={styles.brandTag}>{product.brand}</div>
          <h1 className={styles.pName}>{product.product_name}</h1>
          <DealBadges summary={summary} price={lowestP} />
          {lowestP && (
            <div className={styles.priceBlock}>
              <span className={styles.fromLabel}>From</span>
              <span className={styles.priceMain}>₹{lowestP.toLocaleString('en-IN')}</span>
              {highestP > lowestP && (
                <span className={styles.priceRange}>— ₹{highestP.toLocaleString('en-IN')} across {prices.length} listings</span>
              )}
            </div>
          )}
          {stats && (
            <div className={styles.statsStrip}>
              {stats.platform_count > 0 && <span>🏪 {stats.platform_count} platform{stats.platform_count !== 1 ? 's' : ''}</span>}
              {stats.avg_rating     && <span>⭐ {stats.avg_rating} avg rating</span>}
              {stats.review_count > 0 && <span>💬 {stats.review_count} reviews</span>}
              {stats.max_savings > 0  && <span className={styles.savingsStat}>💰 Save up to ₹{stats.max_savings.toLocaleString('en-IN')}</span>}
              {stats.fake_review_count > 0 && <span className={styles.fakeStat}>⚠ {stats.fake_review_count} suspicious reviews</span>}
            </div>
          )}
          {product.description && <p className={styles.desc}>{product.description}</p>}
        </div>
      </div>

      {/* ── Savings bar ── */}
      {summary?.all_time_high && (
        <div className={styles.savingsBar}>
          {[
            { label: 'Current Best', val: summary.current_lowest,  color: '#10b981' },
            { label: 'All-Time Low', val: summary.all_time_low,    color: '#6366f1' },
            { label: 'Peak Price',   val: summary.all_time_high,   color: '#f59e0b' },
            { label: 'vs Peak',      val: `₹${summary.savings_vs_high?.toLocaleString('en-IN')} (${summary.savings_pct}%)`, color: '#ef4444', raw: true },
          ].map(s => (
            <div key={s.label} className={styles.statBox}>
              <span className={styles.statLabel}>{s.label}</span>
              <span className={styles.statVal} style={{ color: s.color }}>
                {s.raw ? s.val : s.val ? `₹${s.val.toLocaleString('en-IN')}` : '—'}
              </span>
            </div>
          ))}
        </div>
      )}

      {/* ── Price comparison ── */}
      {listings.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sTitle}>
            🏷️ Price Comparison
            <span className={styles.sCnt}>{listings.length} platform{listings.length !== 1 ? 's' : ''}</span>
          </h2>
          {highestP > lowestP && (
            <p className={styles.sSub}>
              Save up to <strong>₹{(highestP - lowestP).toLocaleString('en-IN')}</strong> by choosing the right platform
            </p>
          )}
          <div className={styles.platformList}>
            {listings.map((item, i) => (
              <PlatformRow key={i} item={item} isBest={item.price === lowestP} maxPrice={highestP} />
            ))}
          </div>
        </section>
      )}

      {/* ── AI Verification Score ── */}
      <VerificationSection listings={listings} />

      {/* ── AI Price Prediction ── */}
      <PredictionSection prediction={prediction} />

      {/* ── Price history ── */}
      {history && Object.keys(history).filter(k => k !== 'summary').length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sTitle}>📈 Price History</h2>
          <div className={styles.histGrid}>
            {Object.entries(history)
              .filter(([k]) => k !== 'summary' && Array.isArray(history[k]))
              .map(([plat, pts]) => {
                const meta   = getPM(plat);
                const ps     = pts.map(p => p.price).filter(Boolean);
                if (!ps.length) return null;
                const first  = ps[0], last = ps[ps.length - 1];
                const trend  = last < first ? '↓' : last > first ? '↑' : '→';
                const tColor = trend === '↓' ? '#10b981' : trend === '↑' ? '#ef4444' : '#888';
                return (
                  <div key={plat} className={styles.histCard}>
                    <div className={styles.histHeader}>
                      <span style={{ color: meta.color, fontWeight: 700 }}>{meta.icon} {plat}</span>
                      <span style={{ color: tColor, fontWeight: 900, fontSize: 18 }}>{trend}</span>
                    </div>
                    <Sparkline points={pts} color={meta.color} />
                    <div className={styles.histStats}>
                      <span style={{ color: '#10b981' }}>Low ₹{Math.min(...ps).toLocaleString('en-IN')}</span>
                      <span style={{ color: '#ef4444' }}>High ₹{Math.max(...ps).toLocaleString('en-IN')}</span>
                    </div>
                    <div className={styles.histPoints}>{pts.length} data point{pts.length !== 1 ? 's' : ''}</div>
                  </div>
                );
              })}
          </div>
        </section>
      )}

      {/* ── Local stores ── */}
      {data.local_store_listings?.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.sTitle}>🏪 Nearby Stores</h2>
          <div className={styles.storeList}>
            {data.local_store_listings.map((item, i) => {
              const s = item.store || {};
              const inStock = item.in_stock ?? (item.stock_quantity > 0);
              return (
                <div key={i} className={styles.storeRow}>
                  <div className={styles.storeTop}>
                    <div>
                      <div className={styles.storeName}>{s.store_name}</div>
                      {s.location && <div className={styles.storeLoc}>📍 {s.location}</div>}
                    </div>
                    <div>
                      <div className={styles.storePrice}>₹{item.price?.toLocaleString('en-IN')}</div>
                      <span className={`${styles.stockBadge} ${inStock ? styles.inStock : styles.outStock}`}>
                        {inStock ? '✅ In Stock' : '❌ Out of Stock'}
                      </span>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* ── Reviews ── */}
      {allRevs.length > 0 && (() => {
        const scored  = allRevs.filter(r => r.sentiment_score != null);
        const avgSent = scored.length ? scored.reduce((a, r) => a + r.sentiment_score, 0) / scored.length : null;
        const sentLabel = avgSent == null ? null : avgSent >= 0.6 ? '😊 Mostly Positive' : avgSent >= 0.4 ? '😐 Mixed Sentiment' : '😞 Mostly Negative';
        const sentColor = avgSent == null ? '#888' : avgSent >= 0.6 ? '#16a34a' : avgSent >= 0.4 ? '#d97706' : '#dc2626';
        const fakeCount = allRevs.filter(r => r.is_fake).length;
        return (
          <section className={styles.section}>
            <h2 className={styles.sTitle}>
              💬 Reviews
              <span className={styles.sCnt}>{allRevs.length}</span>
            </h2>
            <div className={styles.sentRow}>
              {sentLabel && (
                <span className={styles.sentChip} style={{ color: sentColor, borderColor: sentColor + '40', background: sentColor + '12' }}>
                  {sentLabel}
                </span>
              )}
              {fakeCount > 0 && (
                <span className={styles.fakeChip}>⚠ {fakeCount} suspicious review{fakeCount !== 1 ? 's' : ''}</span>
              )}
              {avgSent != null && (
                <span className={styles.sentScore}>Avg sentiment: {(avgSent * 100).toFixed(0)}%</span>
              )}
            </div>
            <div className={styles.revGrid}>
              {allRevs.map((r, i) => <ReviewCard key={i} review={r} />)}
            </div>
          </section>
        );
      })()}
    </div>
  );
}
