import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { registerStore } from '../utils/api';
import styles from './StoreRegister.module.css';

export default function StoreRegister() {
  const navigate = useNavigate();
  const [form, setForm] = useState({
    store_name: '', location: '', phone: '', store_rating: '',
  });
  const [errors,    setErrors]   = useState({});
  const [loading,   setLoading]  = useState(false);
  const [submitted, setSubmitted] = useState(null);

  const validate = () => {
    const e = {};
    if (!form.store_name.trim() || form.store_name.trim().length < 2)
      e.store_name = 'Store name must be at least 2 characters';
    if (!form.location.trim() || form.location.trim().length < 3)
      e.location = 'Location must be at least 3 characters';
    if (form.phone) {
      const digits = form.phone.replace(/[\s\-\(\)\+]/g, '');
      if (!/^\d+$/.test(digits) || digits.length < 7 || digits.length > 15)
        e.phone = 'Enter a valid phone number (7–15 digits)';
    }
    if (form.store_rating) {
      const r = parseFloat(form.store_rating);
      if (isNaN(r) || r < 1 || r > 5)
        e.store_rating = 'Rating must be between 1.0 and 5.0';
    }
    return e;
  };

  const handleChange = (field, val) => {
    setForm(f => ({ ...f, [field]: val }));
    if (errors[field]) setErrors(e => ({ ...e, [field]: null }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    const errs = validate();
    if (Object.keys(errs).length) { setErrors(errs); return; }

    setLoading(true);
    try {
      const payload = {
        store_name:   form.store_name.trim(),
        location:     form.location.trim(),
        phone:        form.phone.trim() || null,
        store_rating: form.store_rating ? parseFloat(form.store_rating) : null,
      };
      const res = await registerStore(payload);
      setSubmitted(res.data);
    } catch (err) {
      const msg = err.response?.data?.detail;
      if (Array.isArray(msg)) {
        const fieldErrs = {};
        msg.forEach(e => {
          const field = e.loc?.[e.loc.length - 1];
          if (field) fieldErrs[field] = e.msg;
        });
        setErrors(fieldErrs);
      } else {
        setErrors({ _general: msg || 'Registration failed. Please try again.' });
      }
    } finally {
      setLoading(false);
    }
  };

  if (submitted) {
    return (
      <div className={styles.page}>
        <div className={styles.successCard}>
          <div className={styles.successIcon}>🎉</div>
          <h2 className={styles.successTitle}>Store Registered!</h2>
          <p className={styles.successSub}>
            Your store <strong>{submitted.store_name}</strong> is now on ShopPulse.
          </p>
          <div className={styles.idBox}>
            <div className={styles.idLabel}>Your Store ID — save this to manage your store</div>
            <div className={styles.idValue}>{submitted.store_id}</div>
            <button
              className={styles.copyBtn}
              onClick={() => navigator.clipboard.writeText(submitted.store_id)}
            >
              📋 Copy ID
            </button>
          </div>
          <p className={styles.idHint}>
            Use this ID to log into your Store Dashboard and add products.
          </p>
          <div className={styles.successActions}>
            <button className={styles.primaryBtn}
              onClick={() => navigate(`/store/dashboard?id=${submitted.store_id}`)}>
              Go to Dashboard →
            </button>
            <button className={styles.secondaryBtn} onClick={() => navigate('/stores')}>
              Browse Stores
            </button>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className={styles.page}>
      <div className={styles.header}>
        <h1 className={styles.title}>🏪 Register Your Store</h1>
        <p className={styles.sub}>
          List your local store on ShopPulse so customers can find your prices
          when comparing products online.
        </p>
      </div>

      <div className={styles.formCard}>
        <form onSubmit={handleSubmit} noValidate>

          {errors._general && (
            <div className={styles.generalError}>⚠ {errors._general}</div>
          )}

          <div className={styles.field}>
            <label className={styles.label}>Store Name <span className={styles.req}>*</span></label>
            <input
              className={`${styles.input} ${errors.store_name ? styles.inputError : ''}`}
              type="text"
              placeholder="e.g. Sharma Electronics, Fresh Mart"
              value={form.store_name}
              onChange={e => handleChange('store_name', e.target.value)}
              maxLength={100}
            />
            {errors.store_name && <span className={styles.error}>{errors.store_name}</span>}
          </div>

          <div className={styles.field}>
            <label className={styles.label}>Location / Address <span className={styles.req}>*</span></label>
            <input
              className={`${styles.input} ${errors.location ? styles.inputError : ''}`}
              type="text"
              placeholder="e.g. Banjara Hills, Hyderabad"
              value={form.location}
              onChange={e => handleChange('location', e.target.value)}
              maxLength={200}
            />
            {errors.location && <span className={styles.error}>{errors.location}</span>}
            <span className={styles.hint}>Area/locality name customers will search by</span>
          </div>

          <div className={styles.row}>
            <div className={styles.field}>
              <label className={styles.label}>Phone Number</label>
              <input
                className={`${styles.input} ${errors.phone ? styles.inputError : ''}`}
                type="tel"
                placeholder="9876543210"
                value={form.phone}
                onChange={e => handleChange('phone', e.target.value)}
                maxLength={15}
              />
              {errors.phone && <span className={styles.error}>{errors.phone}</span>}
            </div>
            <div className={styles.field}>
              <label className={styles.label}>Store Rating</label>
              <input
                className={`${styles.input} ${errors.store_rating ? styles.inputError : ''}`}
                type="number"
                placeholder="4.5"
                min="1" max="5" step="0.1"
                value={form.store_rating}
                onChange={e => handleChange('store_rating', e.target.value)}
              />
              {errors.store_rating && <span className={styles.error}>{errors.store_rating}</span>}
              <span className={styles.hint}>Your self-reported rating (1–5)</span>
            </div>
          </div>

          <div className={styles.infoBox}>
            <strong>📋 What happens next?</strong>
            <ul>
              <li>You'll get a unique Store ID after registration</li>
              <li>Use the Store Dashboard to add your products and prices</li>
              <li>Customers see your prices when comparing on ShopPulse</li>
              <li>Update stock and prices anytime via the dashboard</li>
            </ul>
          </div>

          <button type="submit" className={styles.submitBtn} disabled={loading}>
            {loading ? <span className={styles.spinner} /> : '🏪 Register Store'}
          </button>

          <p className={styles.loginHint}>
            Already registered?{' '}
            <button type="button" className={styles.linkBtn}
              onClick={() => navigate('/store/dashboard')}>
              Go to Dashboard
            </button>
          </p>
        </form>
      </div>
    </div>
  );
}
