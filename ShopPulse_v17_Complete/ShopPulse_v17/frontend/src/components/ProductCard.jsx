import { useNavigate } from 'react-router-dom';
import styles from './ProductCard.module.css';

const CATEGORY_EMOJI = {
  Mobiles: '📱', Laptops: '💻', Electronics: '🎧',
  Footwear: '👟', Clothing: '👕', Grocery: '🛒',
  PersonalCare: '🧴', Kitchen: '🍳', Sports: '🏃',
  Appliances: '🌡️', Toys: '🧸', General: '🛍️',
};

const PLATFORM_COLORS = {
  'Amazon': '#FF9900', 'Croma': '#0066CC',
  'Reliance Digital': '#0033A0', 'BigBasket': '#84C225',
};

export default function ProductCard({ product }) {
  const navigate = useNavigate();
  const {
    master_product_id, product_name, brand,
    category, platform_count, min_price,
    platforms, is_deal, image_url,
  } = product;

  const emoji = CATEGORY_EMOJI[category] || '🛍️';

  return (
    <div
      className={`${styles.card} ${is_deal ? styles.dealCard : ''}`}
      onClick={() => navigate(`/product/${master_product_id}`)}
      role="button" tabIndex={0}
      onKeyDown={e => e.key === 'Enter' && navigate(`/product/${master_product_id}`)}
    >
      {/* Deal ribbon */}
      {is_deal && <div className={styles.dealRibbon}>🔥 Deal</div>}

      <div className={styles.imageWrap}>
        {image_url
          ? <img src={image_url} alt={product_name} className={styles.image}
              onError={e => { e.target.style.display='none'; e.target.nextSibling.style.display='flex'; }}
            />
          : null}
        <div className={styles.imageFallback} style={image_url ? {display:'none'} : {}}>{emoji}</div>
      </div>

      <div className={styles.body}>
        {brand && <div className={styles.brand}>{brand}</div>}
        <h3 className={styles.name}>{product_name}</h3>

        {/* Platform dots */}
        {platforms?.length > 0 && (
          <div className={styles.platformDots}>
            {platforms.slice(0, 4).map(p => (
              <span
                key={p}
                className={styles.platformDot}
                style={{ background: PLATFORM_COLORS[p] || '#888' }}
                title={p}
              />
            ))}
            {platforms.length > 4 && (
              <span className={styles.morePlatforms}>+{platforms.length - 4}</span>
            )}
          </div>
        )}

        <div className={styles.footer}>
          {min_price ? (
            <span className={styles.price}>from ₹{min_price.toLocaleString('en-IN')}</span>
          ) : (
            <span className={styles.cta}>Compare prices →</span>
          )}
          {platform_count > 1 && (
            <span className={styles.platformCount}>{platform_count} stores</span>
          )}
          {category && <span className={styles.categoryTag}>{category}</span>}
        </div>
      </div>
    </div>
  );
}
