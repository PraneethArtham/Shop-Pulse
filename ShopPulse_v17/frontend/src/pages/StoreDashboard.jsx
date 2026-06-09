import { useState, useEffect, useCallback } from 'react';
import { useSearchParams, useNavigate } from 'react-router-dom';
import {
  fetchStore, updateStore, deleteStore,
  fetchStoreProducts, addStoreProduct,
  updateStoreProduct, deleteStoreProduct,
  searchProducts,
} from '../utils/api';
import styles from './StoreDashboard.module.css';

export default function StoreDashboard() {
  const [searchParams]  = useSearchParams();
  const navigate        = useNavigate();
  const [storeId, setStoreId]     = useState(searchParams.get('id') || '');
  const [idInput, setIdInput]     = useState(searchParams.get('id') || '');
  const [store,   setStore]       = useState(null);
  const [products, setProducts]   = useState([]);
  const [loading, setLoading]     = useState(false);
  const [error,   setError]       = useState(null);
  const [tab,     setTab]         = useState('products'); // products | edit

  // Add product form
  const [addForm,     setAddForm]     = useState({ product_name: '', master_product_id: '', price: '', stock_quantity: '' });
  const [addErrors,   setAddErrors]   = useState({});
  const [addLoading,  setAddLoading]  = useState(false);
  const [searchSugg,  setSearchSugg]  = useState([]);
  const [searchQuery, setSearchQuery] = useState('');

  // Edit product inline
  const [editingId,   setEditingId]   = useState(null);
  const [editForm,    setEditForm]    = useState({});

  // Edit store form
  const [editStore,   setEditStore]   = useState({});
  const [saveLoading, setSaveLoading] = useState(false);
  const [saveMsg,     setSaveMsg]     = useState('');

  const loadStore = useCallback(async (id) => {
    if (!id.trim()) return;
    setLoading(true); setError(null); setStore(null); setProducts([]);
    try {
      const [s, p] = await Promise.all([fetchStore(id), fetchStoreProducts(id)]);
      setStore(s);
      setProducts(p.products || []);
      setEditStore({ store_name: s.store_name, location: s.location, phone: s.phone || '', store_rating: s.store_rating || '' });
    } catch (e) {
      setError(e.response?.status === 404 ? 'Store not found. Check your Store ID.' : 'Failed to load store.');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { if (storeId) loadStore(storeId); }, [storeId, loadStore]);

  // Autocomplete product search
  useEffect(() => {
    if (!searchQuery.trim() || searchQuery.length < 2) { setSearchSugg([]); return; }
    const t = setTimeout(async () => {
      try {
        const res = await searchProducts(searchQuery, 1, 6);
        setSearchSugg(res?.results || []);
      } catch { setSearchSugg([]); }
    }, 400);
    return () => clearTimeout(t);
  }, [searchQuery]);

  const handleLogin = (e) => {
    e.preventDefault();
    setStoreId(idInput.trim());
  };

  const handleAddProduct = async (e) => {
    e.preventDefault();
    const errs = {};
    if (!addForm.master_product_id) errs.product_name = 'Select a product from the list';
    if (!addForm.price || parseFloat(addForm.price) <= 0) errs.price = 'Enter a valid price';
    if (Object.keys(errs).length) { setAddErrors(errs); return; }

    setAddLoading(true);
    try {
      await addStoreProduct({
        store_id:          storeId,
        master_product_id: addForm.master_product_id,
        product_name:      addForm.product_name,
        price:             parseFloat(addForm.price),
        stock_quantity:    parseInt(addForm.stock_quantity) || 0,
      });
      setAddForm({ product_name: '', master_product_id: '', price: '', stock_quantity: '' });
      setSearchQuery(''); setSearchSugg([]);
      await loadStore(storeId);
    } catch (e) {
      setAddErrors({ _general: e.response?.data?.detail || 'Failed to add product' });
    } finally {
      setAddLoading(false);
    }
  };

  const startEdit = (item) => {
    setEditingId(item.local_product_id);
    setEditForm({ price: item.price, stock_quantity: item.stock_quantity || 0 });
  };

  const saveEdit = async (localProductId) => {
    try {
      await updateStoreProduct(localProductId, {
        price:          parseFloat(editForm.price),
        stock_quantity: parseInt(editForm.stock_quantity) || 0,
      });
      setEditingId(null);
      await loadStore(storeId);
    } catch (e) {
      alert('Failed to update: ' + (e.response?.data?.detail || e.message));
    }
  };

  const handleDelete = async (localProductId, name) => {
    if (!window.confirm(`Remove "${name}" from your store?`)) return;
    try {
      await deleteStoreProduct(localProductId);
      await loadStore(storeId);
    } catch (e) {
      alert('Failed to delete: ' + (e.response?.data?.detail || e.message));
    }
  };

  const handleSaveStore = async (e) => {
    e.preventDefault();
    setSaveLoading(true); setSaveMsg('');
    try {
      await updateStore(storeId, {
        store_name:   editStore.store_name,
        location:     editStore.location,
        phone:        editStore.phone || null,
        store_rating: editStore.store_rating ? parseFloat(editStore.store_rating) : null,
      });
      setSaveMsg('✅ Store details saved');
      await loadStore(storeId);
    } catch (e) {
      setSaveMsg('❌ ' + (e.response?.data?.detail || 'Save failed'));
    } finally {
      setSaveLoading(false);
    }
  };

  const handleDeleteStore = async () => {
    if (!window.confirm(`Delete "${store?.store_name}" and all its listings? This cannot be undone.`)) return;
    try {
      await deleteStore(storeId);
      navigate('/stores');
    } catch (e) {
      alert('Failed: ' + (e.response?.data?.detail || e.message));
    }
  };

  // Login screen
  if (!storeId || (!loading && !store && !error)) {
    return (
      <div className={styles.page}>
        <div className={styles.loginCard}>
          <div className={styles.loginIcon}>🏪</div>
          <h2 className={styles.loginTitle}>Store Dashboard</h2>
          <p className={styles.loginSub}>Enter your Store ID to manage your listings</p>
          <form onSubmit={handleLogin} className={styles.loginForm}>
            <input
              className={styles.loginInput}
              placeholder="Paste your Store ID here"
              value={idInput}
              onChange={e => setIdInput(e.target.value)}
            />
            <button type="submit" className={styles.loginBtn}>Access Dashboard →</button>
          </form>
          <p className={styles.loginHint}>
            Don't have a store yet?{' '}
            <button className={styles.linkBtn} onClick={() => navigate('/store/register')}>
              Register now
            </button>
          </p>
        </div>
      </div>
    );
  }

  if (loading) return (
    <div className={styles.page}>
      <div className={styles.loadingWrap}><div className={styles.spinner} /> Loading your store…</div>
    </div>
  );

  if (error) return (
    <div className={styles.page}>
      <div className={styles.errorCard}>
        <div className={styles.errorIcon}>😕</div>
        <h3>{error}</h3>
        <button className={styles.retryBtn} onClick={() => { setStoreId(''); setError(null); }}>
          Try another ID
        </button>
      </div>
    </div>
  );

  return (
    <div className={styles.page}>
      {/* Header */}
      <div className={styles.storeHeader}>
        <div className={styles.storeInfo}>
          <div className={styles.storeIcon}>🏪</div>
          <div>
            <h1 className={styles.storeName}>{store.store_name}</h1>
            <div className={styles.storeMeta}>
              📍 {store.location}
              {store.phone && <span> · 📞 {store.phone}</span>}
              {store.store_rating && <span> · ⭐ {store.store_rating}</span>}
            </div>
          </div>
        </div>
        <div className={styles.headerStats}>
          <div className={styles.stat}><strong>{products.length}</strong><span>Products</span></div>
          <div className={styles.stat}><strong>{products.filter(p => p.in_stock).length}</strong><span>In Stock</span></div>
        </div>
      </div>

      {/* Tabs */}
      <div className={styles.tabs}>
        <button className={`${styles.tab} ${tab === 'products' ? styles.tabActive : ''}`}
          onClick={() => setTab('products')}>📦 Products</button>
        <button className={`${styles.tab} ${tab === 'edit' ? styles.tabActive : ''}`}
          onClick={() => setTab('edit')}>⚙️ Store Settings</button>
      </div>

      {/* Products Tab */}
      {tab === 'products' && (
        <div>
          {/* Add product form */}
          <div className={styles.addCard}>
            <h3 className={styles.addTitle}>➕ Add Product</h3>
            <form onSubmit={handleAddProduct}>
              {addErrors._general && <div className={styles.formError}>⚠ {addErrors._general}</div>}
              <div className={styles.addRow}>
                <div className={styles.addField} style={{ flex: 2, position: 'relative' }}>
                  <label className={styles.addLabel}>Product</label>
                  <input
                    className={`${styles.addInput} ${addErrors.product_name ? styles.inputError : ''}`}
                    placeholder="Search product name…"
                    value={searchQuery || addForm.product_name}
                    onChange={e => { setSearchQuery(e.target.value); setAddForm(f => ({ ...f, product_name: e.target.value, master_product_id: '' })); }}
                  />
                  {addErrors.product_name && <span className={styles.fieldError}>{addErrors.product_name}</span>}
                  {searchSugg.length > 0 && (
                    <div className={styles.sugg}>
                      {searchSugg.map(p => (
                        <button type="button" key={p.master_product_id} className={styles.suggItem}
                          onClick={() => {
                            setAddForm(f => ({ ...f, product_name: p.product_name, master_product_id: p.master_product_id }));
                            setSearchQuery(''); setSearchSugg([]);
                          }}>
                          <span className={styles.suggName}>{p.product_name}</span>
                          {p.min_price && <span className={styles.suggPrice}>from ₹{p.min_price?.toLocaleString('en-IN')}</span>}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
                <div className={styles.addField}>
                  <label className={styles.addLabel}>Price ₹</label>
                  <input
                    className={`${styles.addInput} ${addErrors.price ? styles.inputError : ''}`}
                    type="number" placeholder="1299" min="1" step="0.01"
                    value={addForm.price}
                    onChange={e => setAddForm(f => ({ ...f, price: e.target.value }))}
                  />
                  {addErrors.price && <span className={styles.fieldError}>{addErrors.price}</span>}
                </div>
                <div className={styles.addField}>
                  <label className={styles.addLabel}>Stock Qty</label>
                  <input
                    className={styles.addInput}
                    type="number" placeholder="10" min="0"
                    value={addForm.stock_quantity}
                    onChange={e => setAddForm(f => ({ ...f, stock_quantity: e.target.value }))}
                  />
                </div>
                <button type="submit" className={styles.addBtn} disabled={addLoading}>
                  {addLoading ? <span className={styles.spinner} /> : 'Add'}
                </button>
              </div>
            </form>
          </div>

          {/* Products list */}
          {products.length === 0 ? (
            <div className={styles.emptyProducts}>
              <span>📦</span>
              <p>No products listed yet. Add your first product above.</p>
            </div>
          ) : (
            <div className={styles.productTable}>
              <div className={styles.tableHead}>
                <span>Product</span><span>Price</span><span>Stock</span><span>Status</span><span>Actions</span>
              </div>
              {products.map(item => (
                <div key={item.local_product_id} className={styles.tableRow}>
                  <span className={styles.prodName}>{item.product_name}</span>

                  {editingId === item.local_product_id ? (
                    <>
                      <input className={styles.editInput} type="number" value={editForm.price}
                        onChange={e => setEditForm(f => ({ ...f, price: e.target.value }))} />
                      <input className={styles.editInput} type="number" value={editForm.stock_quantity}
                        onChange={e => setEditForm(f => ({ ...f, stock_quantity: e.target.value }))} />
                      <span />
                      <div className={styles.actions}>
                        <button className={styles.saveBtn} onClick={() => saveEdit(item.local_product_id)}>Save</button>
                        <button className={styles.cancelBtn} onClick={() => setEditingId(null)}>Cancel</button>
                      </div>
                    </>
                  ) : (
                    <>
                      <span className={styles.prodPrice}>₹{item.price?.toLocaleString('en-IN')}</span>
                      <span className={styles.prodStock}>{item.stock_quantity || 0}</span>
                      <span className={`${styles.stockBadge} ${item.in_stock ? styles.inStock : styles.outStock}`}>
                        {item.in_stock ? '✅ In Stock' : '❌ Out'}
                      </span>
                      <div className={styles.actions}>
                        <button className={styles.editBtn} onClick={() => startEdit(item)}>Edit</button>
                        <button className={styles.delBtn} onClick={() => handleDelete(item.local_product_id, item.product_name)}>Remove</button>
                      </div>
                    </>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      )}

      {/* Settings Tab */}
      {tab === 'edit' && (
        <div className={styles.settingsCard}>
          <h3 className={styles.settingsTitle}>Store Details</h3>
          <form onSubmit={handleSaveStore}>
            <div className={styles.settingsField}>
              <label className={styles.addLabel}>Store Name</label>
              <input className={styles.addInput} value={editStore.store_name || ''}
                onChange={e => setEditStore(s => ({ ...s, store_name: e.target.value }))} />
            </div>
            <div className={styles.settingsField}>
              <label className={styles.addLabel}>Location</label>
              <input className={styles.addInput} value={editStore.location || ''}
                onChange={e => setEditStore(s => ({ ...s, location: e.target.value }))} />
            </div>
            <div className={styles.settingsRow}>
              <div className={styles.settingsField}>
                <label className={styles.addLabel}>Phone</label>
                <input className={styles.addInput} value={editStore.phone || ''}
                  onChange={e => setEditStore(s => ({ ...s, phone: e.target.value }))} />
              </div>
              <div className={styles.settingsField}>
                <label className={styles.addLabel}>Rating (1–5)</label>
                <input className={styles.addInput} type="number" min="1" max="5" step="0.1"
                  value={editStore.store_rating || ''}
                  onChange={e => setEditStore(s => ({ ...s, store_rating: e.target.value }))} />
              </div>
            </div>
            {saveMsg && <div className={styles.saveMsg}>{saveMsg}</div>}
            <button type="submit" className={styles.saveStoreBtn} disabled={saveLoading}>
              {saveLoading ? <span className={styles.spinner} /> : '💾 Save Changes'}
            </button>
          </form>

          <div className={styles.dangerZone}>
            <h4 className={styles.dangerTitle}>⚠ Danger Zone</h4>
            <p className={styles.dangerDesc}>Deleting your store removes all listings permanently.</p>
            <button className={styles.deleteStoreBtn} onClick={handleDeleteStore}>
              🗑 Delete Store
            </button>
          </div>
        </div>
      )}
    </div>
  );
}
