import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { fetchCategories } from '../utils/api';
import styles from './Home.module.css';

const POPULAR = [
  'boAt Airdopes 141 under ₹1500',
  'Cadbury Dairy Milk',
  'Trimmer under ₹500',
  'Voltas 1.5 ton AC',
  'Face wash under ₹200',
  'Samsung Galaxy S24',
];

const PLATFORMS = [
  { name: 'Amazon',           color: '#FF9900', bg: '#fff8ee', emoji: '🛒', tag: 'Electronics & more' },
  { name: 'Croma',            color: '#0055b3', bg: '#eff6ff', emoji: '🏪', tag: 'Gadgets & tech' },
  { name: 'Reliance Digital', color: '#c8102e', bg: '#fff1f2', emoji: '⚡', tag: 'Appliances' },
  { name: 'BigBasket',        color: '#84b135', bg: '#f3fae8', emoji: '🛍️', tag: 'Grocery & care' },
];

const CAT_META = {
  Electronics:  { emoji: '🎧', color: '#6366f1' },
  Mobiles:      { emoji: '📱', color: '#f59e0b' },
  Laptops:      { emoji: '💻', color: '#3b82f6' },
  Appliances:   { emoji: '❄️', color: '#06b6d4' },
  Grocery:      { emoji: '🛒', color: '#16a34a' },
  PersonalCare: { emoji: '🧴', color: '#ec4899' },
  Kitchen:      { emoji: '🍳', color: '#8b5cf6' },
  Footwear:     { emoji: '👟', color: '#f97316' },
  Clothing:     { emoji: '👕', color: '#14b8a6' },
  Sports:       { emoji: '🏃', color: '#10b981' },
  General:      { emoji: '🛍️', color: '#6b7280' },
};

const NLP_DEMOS = [
  { query: 'boat airdopes 141 under ₹1500', tag: 'Brand + Model + Price' },
  { query: 'wireless headphone with ANC',    tag: 'Attribute detection' },
  { query: 'voltas 1.5 ton split ac',        tag: 'Spec + Category' },
  { query: 'compare samsung vs oneplus',     tag: 'Intent: Compare' },
  { query: 'cadbury dairy milk chocolate',   tag: 'Grocery + Brand' },
  { query: 'face wash under ₹200',           tag: 'Category + Budget' },
];

export default function Home() {
  const navigate = useNavigate();
  const [query, setQuery]       = useState('');
  const [categories, setCats]   = useState([]);
  const [nlpIdx, setNlpIdx]     = useState(0);

  useEffect(() => {
    fetchCategories().then(d => setCats(d.categories || [])).catch(() => {});
  }, []);

  useEffect(() => {
    const t = setInterval(() => setNlpIdx(i => (i + 1) % NLP_DEMOS.length), 2800);
    return () => clearInterval(t);
  }, []);

  const go = (q) => {
    const t = (q || query).trim();
    if (t) navigate(`/search?q=${encodeURIComponent(t)}`);
  };

  return (
    <div className={styles.page}>

      {/* ── Hero ── */}
      <section className={styles.hero}>
        <div className={styles.heroText}>
          <span className={styles.pill}>🇮🇳 India's Smart Price Comparator</span>
          <h1 className={styles.h1}>
            Compare prices across<br />
            <span className={styles.highlight}>4 platforms</span> in seconds
          </h1>
          <p className={styles.sub}>
            Type naturally — <strong>"trimmer under ₹500"</strong> or <strong>"Voltas 1.5 ton AC"</strong>.
            Our NLP engine understands you and finds the best deal instantly.
          </p>

          <form className={styles.heroForm} onSubmit={e => { e.preventDefault(); go(); }}>
            <input
              className={styles.heroInput}
              value={query}
              onChange={e => setQuery(e.target.value)}
              placeholder='Search any product with budget…'
              autoFocus
            />
            <button type="submit" className={styles.heroBtn}>🔍 Search</button>
          </form>

          <div className={styles.chips}>
            {POPULAR.map(p => (
              <button key={p} className={styles.chip} onClick={() => go(p)}>{p}</button>
            ))}
          </div>
        </div>

        {/* NLP Demo Card */}
        <div className={styles.nlpDemo}>
          <div className={styles.nlpTop}>
            <span className={styles.nlpLabel}>🧠 Smart NLP Search</span>
            <span className={styles.nlpLive}>● Live</span>
          </div>
          <div className={styles.nlpExample} key={nlpIdx}>
            <div className={styles.nlpQ}>"{NLP_DEMOS[nlpIdx].query}"</div>
            <div className={styles.nlpTagWrap}>
              <span className={styles.nlpTag}>{NLP_DEMOS[nlpIdx].tag}</span>
            </div>
          </div>
          <div className={styles.nlpPills}>
            {NLP_DEMOS.map((_, i) => (
              <button
                key={i}
                className={`${styles.nlpPill} ${i === nlpIdx ? styles.nlpPillActive : ''}`}
                onClick={() => setNlpIdx(i)}
              />
            ))}
          </div>
          <div className={styles.nlpFooter}>
            Powered by <strong>LinearSVC</strong> + <strong>TF-IDF</strong> cosine similarity
          </div>
        </div>
      </section>

      {/* ── Stats strip ── */}
      <div className={styles.statsStrip}>
        {[
          { n: '4',    l: 'Platforms tracked' },
          { n: 'Live', l: 'Crawled prices' },
          { n: 'NLP',  l: 'Natural language' },
          { n: 'Free', l: 'Always free' },
        ].map(s => (
          <div key={s.l} className={styles.stat}>
            <span className={styles.statN}>{s.n}</span>
            <span className={styles.statL}>{s.l}</span>
          </div>
        ))}
      </div>

      {/* ── Platforms ── */}
      <section className={styles.section}>
        <h2 className={styles.h2}>Platforms we track</h2>
        <p className={styles.sectionSub}>Prices are crawled live — every search gets fresh data</p>
        <div className={styles.platformGrid}>
          {PLATFORMS.map(p => (
            <div key={p.name} className={styles.platformCard}
              style={{ '--pc': p.color, '--pcbg': p.bg }}>
              <div className={styles.platformIcon}>{p.emoji}</div>
              <div className={styles.platformName}>{p.name}</div>
              <div className={styles.platformTag}>{p.tag}</div>
              <div className={styles.platformDot} />
            </div>
          ))}
        </div>
      </section>

      {/* ── Categories ── */}
      {categories.length > 0 && (
        <section className={styles.section}>
          <h2 className={styles.h2}>Browse by category</h2>
          <div className={styles.catGrid}>
            {categories.map(cat => {
              const m = CAT_META[cat] || CAT_META.General;
              return (
                <button key={cat} className={styles.catCard}
                  style={{ '--cc': m.color }}
                  onClick={() => navigate(`/category/${cat}`)}>
                  <span className={styles.catEmoji}>{m.emoji}</span>
                  <span className={styles.catName}>{cat}</span>
                </button>
              );
            })}
          </div>
        </section>
      )}

      {/* ── NLP Examples ── */}
      <section className={styles.section}>
        <h2 className={styles.h2}>Try these smart searches</h2>
        <p className={styles.sectionSub}>Click any example to see NLP in action</p>
        <div className={styles.examples}>
          {NLP_DEMOS.map((d, i) => (
            <button key={i} className={styles.exRow} onClick={() => go(d.query)}>
              <span className={styles.exQ}>"{d.query}"</span>
              <span className={styles.exTag}>{d.tag}</span>
            </button>
          ))}
        </div>
      </section>


      {/* ── Local Stores ── */}
      <section className={styles.section}>
        <h2 className={styles.h2}>🏪 Local Stores on ShopPulse</h2>
        <p className={styles.sectionSub}>Compare prices from local shops in your city alongside online platforms</p>
        <div className={styles.storeCtaGrid}>
          <div className={styles.storeCtaCard} onClick={() => navigate('/stores')}>
            <div className={styles.storeCtaIcon}>🔍</div>
            <div className={styles.storeCtaTitle}>Browse Local Stores</div>
            <div className={styles.storeCtaSub}>Find stores in your area and compare their prices</div>
          </div>
          <div className={styles.storeCtaCard} onClick={() => navigate('/store/register')}>
            <div className={styles.storeCtaIcon}>🏪</div>
            <div className={styles.storeCtaTitle}>Register Your Store</div>
            <div className={styles.storeCtaSub}>List your store and reach customers comparing prices online</div>
          </div>
          <div className={styles.storeCtaCard} onClick={() => navigate('/store/dashboard')}>
            <div className={styles.storeCtaIcon}>📦</div>
            <div className={styles.storeCtaTitle}>Manage Your Listings</div>
            <div className={styles.storeCtaSub}>Update prices and stock from your store dashboard</div>
          </div>
        </div>
      </section>

    </div>
  );
}
