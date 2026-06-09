/**
 * Format price in Indian Rupees
 */
export const formatPrice = (price) => {
  if (price == null) return '—';
  return `₹${Number(price).toLocaleString('en-IN')}`;
};

/**
 * Render star rating string
 */
export const renderStars = (rating) => {
  if (!rating) return '';
  const full = Math.floor(rating);
  const half = rating % 1 >= 0.5 ? 1 : 0;
  const empty = 5 - full - half;
  return '★'.repeat(full) + (half ? '½' : '') + '☆'.repeat(empty);
};

/**
 * Truncate text to a max length
 */
export const truncate = (str, max = 60) => {
  if (!str) return '';
  return str.length > max ? str.slice(0, max) + '…' : str;
};

/**
 * Platform color map — all active platforms
 */
export const PLATFORM_COLORS = {
  Amazon:            { bg: 'rgba(255,153,0,0.12)',   color: '#FF9900' },
  Croma:             { bg: 'rgba(0,102,204,0.12)',   color: '#0066CC' },
  'Reliance Digital':{ bg: 'rgba(0,51,160,0.12)',    color: '#0033A0' },
  BigBasket:         { bg: 'rgba(132,194,37,0.12)',  color: '#84C225' },
  Flipkart:          { bg: 'rgba(39,109,255,0.12)',  color: '#276DFF' },
  Meesho:            { bg: 'rgba(158,42,204,0.12)',  color: '#9E2ACC' },
};

/**
 * Category icons — including new Grocery / PersonalCare
 */
export const CATEGORY_ICONS = {
  Electronics:  '🎧',
  Mobiles:      '📱',
  Laptops:      '💻',
  Footwear:     '👟',
  Clothing:     '👕',
  Kitchen:      '🍳',
  Beauty:       '💄',
  Books:        '📚',
  Toys:         '🧸',
  Sports:       '⚽',
  Grocery:      '🛒',
  PersonalCare: '🧴',
  Appliances:   '🌡️',
  General:      '🛍️',
};
