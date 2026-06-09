import axios from 'axios';

const API = axios.create({
  baseURL: process.env.REACT_APP_API_URL || 'http://127.0.0.1:8000',
  timeout: 90000,
});

API.interceptors.response.use(
  (response) => response,
  (error) => {
    console.error('API Error:', error.response?.data || error.message);
    return Promise.reject(error);
  }
);

export default API;

// Products
export const fetchCategories = () => API.get('/categories').then(r => r.data);
export const fetchProductsByCategory = (category, page = 1, limit = 20, sort = null) =>
  API.get('/products', { params: { category, page, limit, sort } }).then(r => r.data);
export const fetchProductDetails    = (id) => API.get(`/products/${id}`).then(r => r.data);
export const fetchPriceHistory      = (id) => API.get(`/products/${id}/price-history`).then(r => r.data);
export const fetchPricePrediction   = (id) => API.get(`/products/${id}/predict`).then(r => r.data);

// Search
export const searchProducts = (query, page = 1, limit = 20, forceCrawl = false) =>
  API.get('/search', { params: { query, page, limit, force_crawl: forceCrawl }, timeout: 90000 }).then(r => r.data);

export const parseQuery = (query) =>
  API.get('/search/parse', { params: { query }, timeout: 5000 }).then(r => r.data);

// Crawl
export const fetchCrawlStatus = (query) =>
  API.get('/crawl/status', { params: { query }, timeout: 5000 }).then(r => r.data);
export const triggerCrawl = (query) =>
  API.get('/crawl/trigger', { params: { query } }).then(r => r.data);
export const testCrawlers = (query, platform = 'all') =>
  API.get('/crawl/test', { params: { query, platform }, timeout: 120000 }).then(r => r.data);

// Local Stores
export const fetchStores       = (search = '') => API.get('/localstores', { params: search ? { search } : {} }).then(r => r.data);
export const fetchStore        = (id)           => API.get(`/localstores/${id}`).then(r => r.data);
export const registerStore     = (data)         => API.post('/localstores', data).then(r => r.data);
export const updateStore       = (id, data)     => API.put(`/localstores/${id}`, data).then(r => r.data);
export const deleteStore       = (id)           => API.delete(`/localstores/${id}`).then(r => r.data);
export const fetchStoreProducts= (storeId)      => API.get(`/localstores/${storeId}/products`).then(r => r.data);
export const addStoreProduct   = (data)         => API.post('/localstoreproducts', data).then(r => r.data);
export const updateStoreProduct= (id, data)     => API.put(`/localstoreproducts/${id}`, data).then(r => r.data);
export const deleteStoreProduct= (id)           => API.delete(`/localstoreproducts/${id}`).then(r => r.data);
export const fetchLocalProducts= (masterProductId) => API.get(`/localstoreproducts/${masterProductId}`).then(r => r.data);
