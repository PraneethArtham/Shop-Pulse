import { useState, useEffect, useRef, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import { searchProducts, fetchCrawlStatus } from '../utils/api';
import ProductCard from '../components/ProductCard';
import { CardSkeleton } from '../components/Loader';
import EmptyState from '../components/EmptyState';
import styles from './Search.module.css';

const POPULAR = [
  'boAt Airdopes 141 under ₹1500', 'Cadbury Dairy Milk',
  'Voltas 1.5 ton AC', 'Trimmer under ₹500',
  'Sony WH-1000XM5', 'Samsung Galaxy S24',
  'Face wash under ₹200', 'Amul Butter',
];

const CATEGORY_ICONS = {
  Electronics: '🎧', Mobiles: '📱', Laptops: '💻',
  Grocery: '🛒', PersonalCare: '🧴', Appliances: '🌡️',
  Kitchen: '🍳', Footwear: '👟', Clothing: '👕', Sports: '⚽',
};
const INTENT_META = {
  find_cheapest:      { label: 'Find Cheapest',  color: '#10b981' },
  compare:            { label: 'Compare',         color: '#6366f1' },
  check_availability: { label: 'Check Stock',     color: '#f59e0b' },
  review_check:       { label: 'Check Reviews',   color: '#3b82f6' },
};

// ── NLP Understanding Panel ─────────────────────────────────────────────────
function NlpPanel({ parsed, query }) {
  if (!parsed) return null;

  const hasData = parsed.brand || parsed.model || parsed.category ||
                  parsed.price_max || parsed.price_min ||
                  (parsed.attributes?.length > 0);
  if (!hasData) return null;

  const intent = INTENT_META[parsed.intent];

  return (
    <div className={styles.nlpPanel}>
      {/* Header */}
      <div className={styles.nlpHeader}>
        <div className={styles.nlpTitle}>
          <span className={styles.nlpBrainIcon}>🧠</span>
          <span>NLP understood your query</span>
          <span className={styles.nlpEngine}>sklearn TF-IDF</span>
        </div>
        {intent && (
          <span className={styles.nlpIntent} style={{ color: intent.color, borderColor: intent.color + '40', background: intent.color + '12' }}>
            {intent.label}
          </span>
        )}
      </div>

      {/* Chips row */}
      <div className={styles.nlpChipsRow}>
        {parsed.brand && (
          <div className={styles.nlpChip} data-type="brand">
            <span className={styles.nlpChipLabel}>Brand</span>
            <span className={styles.nlpChipValue}>🏷️ {parsed.brand}</span>
          </div>
        )}
        {parsed.model && (
          <div className={styles.nlpChip} data-type="model">
            <span className={styles.nlpChipLabel}>Model</span>
            <span className={styles.nlpChipValue}>🔢 {parsed.model}</span>
          </div>
        )}
        {parsed.category && (
          <div className={styles.nlpChip} data-type="category">
            <span className={styles.nlpChipLabel}>Category</span>
            <span className={styles.nlpChipValue}>
              {CATEGORY_ICONS[parsed.category] || '📂'} {parsed.category}
            </span>
          </div>
        )}
        {(parsed.price_min || parsed.price_max) && (
          <div className={styles.nlpChip} data-type="price">
            <span className={styles.nlpChipLabel}>Price</span>
            <span className={styles.nlpChipValue}>
              💰 {parsed.price_min && parsed.price_max
                ? `₹${parsed.price_min.toLocaleString('en-IN')} – ₹${parsed.price_max.toLocaleString('en-IN')}`
                : parsed.price_max
                ? `Under ₹${parsed.price_max.toLocaleString('en-IN')}`
                : `Above ₹${parsed.price_min.toLocaleString('en-IN')}`}
            </span>
          </div>
        )}
        {parsed.attributes?.slice(0, 3).map(a => (
          <div key={a} className={styles.nlpChip} data-type="attr">
            <span className={styles.nlpChipLabel}>Feature</span>
            <span className={styles.nlpChipValue}>✨ {a.replace(/_/g, ' ')}</span>
          </div>
        ))}
        {parsed.synonyms?.slice(0, 2).map(s => (
          <div key={s} className={styles.nlpChip} data-type="syn">
            <span className={styles.nlpChipLabel}>Also searching</span>
            <span className={styles.nlpChipValue}>↔️ {s}</span>
          </div>
        ))}
      </div>

      {/* Search terms pipeline */}
      {parsed.search_terms?.length > 0 && (
        <div className={styles.nlpPipeline}>
          <span className={styles.nlpPipelineLabel}>Search strategy:</span>
          <div className={styles.nlpTerms}>
            {parsed.search_terms.slice(0, 4).map((t, i) => (
              <span key={i} className={styles.nlpTerm}>
                {i > 0 && <span className={styles.nlpArrow}>→</span>}
                <code>{t}</code>
                {i === 0 && <span className={styles.nlpPrimary}>primary</span>}
              </span>
            ))}
            {parsed.search_terms.length > 4 && (
              <span className={styles.nlpMoreTerms}>+{parsed.search_terms.length - 4} more</span>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ── Crawl Banner ─────────────────────────────────────────────────────────────
function CrawlBanner({ status, query }) {
  if (!status || status.status === 'idle') return null;
  const s = status.status;
  return (
    <div className={`${styles.crawlBanner} ${styles['crawl_' + s]}`}>
      <div className={styles.crawlLeft}>
        {s === 'crawling' && <div className={styles.crawlSpinner} />}
        {s === 'done'     && <span>✅</span>}
        {s === 'error'    && <span>⚠️</span>}
        <div>
          <div className={styles.crawlTitle}>
            {s === 'crawling' ? `🌐 Crawling live — "${query}"` : s === 'done' ? 'Live crawl complete' : 'Crawl issues'}
          </div>
          <div className={styles.crawlSub}>{s === 'crawling'
            ? 'Scanning Amazon · Croma · Reliance Digital · BigBasket'
            : status.message}
          </div>
        </div>
      </div>
      {s === 'crawling' && (
        <div className={styles.crawlPlatforms}>
          {['🛒 Amazon', '🏪 Croma', '⚡ Reliance', '🛍️ BigBasket'].map(p => (
            <span key={p} className={styles.crawlChip}>{p}</span>
          ))}
        </div>
      )}
      {s === 'done' && status.count > 0 && (
        <strong className={styles.crawlCount}>{status.count} new products saved</strong>
      )}
    </div>
  );
}

// ── Sort bar ──────────────────────────────────────────────────────────────────
function SortBar({ sort, onSort, count, source }) {
  return (
    <div className={styles.sortBar}>
      <span className={styles.resultCount}>
        <strong>{count}</strong> result{count !== 1 ? 's' : ''}
        {source === 'db'      && <span className={styles.srcBadge}>⚡ Cached</span>}
        {source === 'crawled' && <span className={`${styles.srcBadge} ${styles.srcLive}`}>🌐 Live</span>}
      </span>
      <div className={styles.sortBtns}>
        {[
          { k: 'relevance',  l: 'Best Match' },
          { k: 'price_asc',  l: 'Price ↑' },
          { k: 'price_desc', l: 'Price ↓' },
          { k: 'platform',   l: 'Most Platforms' },
        ].map(s => (
          <button key={s.k}
            className={`${styles.sortBtn} ${sort === s.k ? styles.sortActive : ''}`}
            onClick={() => onSort(s.k)}>
            {s.l}
          </button>
        ))}
      </div>
    </div>
  );
}

// ── Main ───────────────────────────────────────────────────────────────────────
export default function Search() {
  const [searchParams, setSearchParams] = useSearchParams();
  const urlQuery = searchParams.get('q') || '';

  const [inputVal,    setInputVal]    = useState(urlQuery);
  const [submitted,   setSub]         = useState('');
  const [results,     setResults]     = useState([]);
  const [allResults,  setAllResults]  = useState([]);
  const [loading,     setLoading]     = useState(false);
  const [error,       setError]       = useState(null);
  const [source,      setSource]      = useState(null);
  const [parsed,      setParsed]      = useState(null);
  const [crawlStatus, setCrawlStatus] = useState(null);
  const [sort,        setSort]        = useState('relevance');
  const [suggestions, setSuggestions] = useState([]);
  const [showSug,     setShowSug]     = useState(false);

  const pollRef     = useRef(null);
  const activeQuery = useRef('');

  const stopPolling = () => { if (pollRef.current) { clearInterval(pollRef.current); pollRef.current = null; } };
  const pollCountRef = useRef(0);
  const startPolling = (q) => {
    stopPolling();
    pollCountRef.current = 0;
    pollRef.current = setInterval(async () => {
      pollCountRef.current += 1;
      // Hard stop after 30 polls (60 seconds)
      if (pollCountRef.current >= 30) {
        stopPolling();
        setCrawlStatus(s => s ? { ...s, status: 'error', message: 'Search is taking longer than usual. Try again.' } : s);
        return;
      }
      try {
        const s = await fetchCrawlStatus(q);
        setCrawlStatus(s);
        if (s.status === 'done' || s.status === 'error') stopPolling();
      } catch (_) {}
    }, 2000);
  };
  useEffect(() => () => stopPolling(), []);

  // Client-side sort
  useEffect(() => {
    if (!allResults.length) return;
    let sorted = [...allResults];
    if (sort === 'price_asc')  sorted.sort((a, b) => (a.min_price || Infinity) - (b.min_price || Infinity));
    if (sort === 'price_desc') sorted.sort((a, b) => (b.min_price || 0) - (a.min_price || 0));
    if (sort === 'platform')   sorted.sort((a, b) => (b.platform_count || 0) - (a.platform_count || 0));
    setResults(sorted);
  }, [sort, allResults]);

  // Autocomplete
  useEffect(() => {
    if (!inputVal.trim() || inputVal.length < 2) { setSuggestions([]); return; }
    const q = inputVal.toLowerCase();
    setSuggestions(POPULAR.filter(p => p.toLowerCase().includes(q) && p.toLowerCase() !== q).slice(0, 5));
  }, [inputVal]);

  const runSearch = useCallback(async (q) => {
    if (!q.trim()) return;
    const trimmed = q.trim();
    stopPolling();
    setLoading(true); setError(null); setAllResults([]); setResults([]);
    setSource(null); setCrawlStatus(null); setParsed(null);
    setSub(trimmed); setInputVal(trimmed); setSearchParams({ q: trimmed });
    setSort('relevance'); setSuggestions([]); setShowSug(false);
    activeQuery.current = trimmed;

    const bannerTimer = setTimeout(() => {
      if (activeQuery.current === trimmed) {
        setCrawlStatus({ status: 'crawling', query: trimmed, message: '', count: 0 });
        startPolling(trimmed);
      }
    }, 1200);

    try {
      const data = await searchProducts(trimmed);
      clearTimeout(bannerTimer);
      if (activeQuery.current !== trimmed) return;
      const res = data.results || [];
      setAllResults(res); setResults(res);
      setSource(data.source);
      setParsed(data.parsed || null);
      if (data.crawl_triggered) {
        setCrawlStatus({ status: 'done', query: trimmed, message: data.message, count: data.count || 0 });
        stopPolling();
      } else {
        setCrawlStatus(null); stopPolling();
      }
    } catch (e) {
      clearTimeout(bannerTimer);
      if (activeQuery.current === trimmed) {
        setError(e.message || 'Search failed'); stopPolling(); setCrawlStatus(null);
      }
    } finally {
      if (activeQuery.current === trimmed) setLoading(false);
    }
  }, [setSearchParams]);

  useEffect(() => { if (urlQuery) runSearch(urlQuery); }, [urlQuery]);

  return (
    <div className={styles.page}>
      {/* ── Search bar ── */}
      <div className={styles.searchSection}>
        <form className={styles.searchForm} onSubmit={e => { e.preventDefault(); runSearch(inputVal); }}>
          <div className={styles.searchWrap}>
            <span className={styles.searchIcon}>🔍</span>
            <input
              className={styles.searchInput}
              type="text"
              placeholder='Try "boAt Airdopes 141 under ₹1500" · "Voltas 1.5 ton AC" · "face wash under ₹200"'
              value={inputVal}
              onChange={e => { setInputVal(e.target.value); setShowSug(true); }}
              onFocus={() => setShowSug(true)}
              onBlur={() => setTimeout(() => setShowSug(false), 150)}
              autoFocus
            />
            {inputVal && (
              <button type="button" className={styles.clearBtn}
                onClick={() => { setInputVal(''); setSub(''); setAllResults([]); setResults([]); }}>✕</button>
            )}
          </div>
          <button className={styles.searchBtn} type="submit" disabled={loading}>
            {loading ? <span className={styles.btnSpinner} /> : 'Search'}
          </button>
        </form>

        {/* Autocomplete */}
        {showSug && suggestions.length > 0 && (
          <div className={styles.suggestions}>
            {suggestions.map(s => (
              <button key={s} className={styles.sugItem} onMouseDown={() => runSearch(s)}>
                <span>🔍</span>{s}
              </button>
            ))}
          </div>
        )}
      </div>

      {/* ── Popular (pre-search) ── */}
      {!submitted && (
        <div className={styles.popular}>
          <div className={styles.popularHeader}>
            <span className={styles.popularLabel}>Try these</span>
            <span className={styles.nlpHint}>🧠 NLP-powered — understands natural language</span>
          </div>
          <div className={styles.chips}>{POPULAR.map(s => (
            <button key={s} className={styles.chip} onClick={() => runSearch(s)}>{s}</button>
          ))}</div>
        </div>
      )}

      {/* ── NLP Panel ── */}
      {submitted && <NlpPanel parsed={parsed} query={submitted} />}

      {/* ── Crawl banner ── */}
      {submitted && <CrawlBanner status={crawlStatus} query={submitted} />}

      {/* ── Results ── */}
      {(submitted || loading) && (
        <div className={styles.resultsSection}>
          {!loading && results.length > 0 && (
            <SortBar sort={sort} onSort={setSort} count={results.length} source={source} />
          )}
          {error ? (
            <EmptyState icon="⚠️" title="Search failed" subtitle={error} />
          ) : loading ? (
            <div className={styles.grid}>
              {Array.from({ length: 8 }).map((_, i) => <CardSkeleton key={i} />)}
            </div>
          ) : results.length === 0 && crawlStatus?.status !== 'crawling' ? (
            <div className={styles.noResults}>
              <span>🔍</span>
              <h3>No results for "<em>{submitted}</em>"</h3>
              <p>Try rephrasing — remove extra words or check spelling.</p>
              <div className={styles.chips}>
                {POPULAR.slice(0, 4).map(s => (
                  <button key={s} className={styles.chip} onClick={() => runSearch(s)}>{s}</button>
                ))}
              </div>
            </div>
          ) : results.length === 0 && crawlStatus?.status === 'crawling' ? (
            <div className={styles.crawlingPlaceholder}>
              <div className={styles.crawlPulse}>🌐</div>
              <p>Scanning platforms for <strong>"{submitted}"</strong>…</p>
              <p className={styles.crawlHint}>Live crawl takes 15–30 seconds for new products</p>
            </div>
          ) : (
            <div className={`${styles.grid} stagger`}>
              {results.map(p => <ProductCard key={p.master_product_id} product={p} />)}
            </div>
          )}
        </div>
      )}
    </div>
  );
}
