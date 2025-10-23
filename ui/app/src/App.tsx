import { Navigate, Route, Routes } from 'react-router-dom';
import Layout from './components/Layout';
import RunListPage from './pages/RunListPage';
import RunDetailPage from './pages/RunDetailPage';
import NotFoundPage from './pages/NotFoundPage';

const App = () => {
  return (
    <Layout>
      <Routes>
        <Route path="/" element={<RunListPage />} />
        <Route path="/runs/:runId" element={<RunDetailPage />} />
        <Route path="/runs/:runId/logs" element={<RunDetailPage initialTab="logs" />} />
        <Route path="/runs/:runId/artifacts" element={<RunDetailPage initialTab="artifacts" />} />
        <Route path="/runs/:runId/metrics" element={<RunDetailPage initialTab="metrics" />} />
        <Route path="/home" element={<Navigate to="/" replace />} />
        <Route path="*" element={<NotFoundPage />} />
      </Routes>
    </Layout>
  );
};

export default App;
