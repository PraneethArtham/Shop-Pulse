import { BrowserRouter, Routes, Route } from 'react-router-dom';
import Navbar          from './components/Navbar';
import Home            from './pages/Home';
import Category        from './pages/Category';
import ProductDetails  from './pages/ProductDetails';
import Search          from './pages/Search';
import CrawlerTest     from './pages/CrawlerTest';
import StoresList      from './pages/StoresList';
import StoreRegister   from './pages/StoreRegister';
import StoreDashboard  from './pages/StoreDashboard';

export default function App() {
  return (
    <BrowserRouter>
      <Navbar />
      <main>
        <Routes>
          <Route path="/"                       element={<Home />} />
          <Route path="/category/:categoryName" element={<Category />} />
          <Route path="/product/:id"            element={<ProductDetails />} />
          <Route path="/search"                 element={<Search />} />
          <Route path="/crawl-test"             element={<CrawlerTest />} />
          <Route path="/stores"                 element={<StoresList />} />
          <Route path="/store/register"         element={<StoreRegister />} />
          <Route path="/store/dashboard"        element={<StoreDashboard />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}
