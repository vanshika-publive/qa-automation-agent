import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import Layout from './components/Layout';
import Collections from './pages/Collections';
import CollectionDetail from './pages/CollectionDetail';
import Executions from './pages/Executions';
import ExecutionDetail from './pages/ExecutionDetail';
import BatchExecutionStatus from './pages/BatchExecutionStatus';
import Environments from './pages/Environments';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      retry: 1,
    },
  },
});

export default function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <BrowserRouter>
        <Routes>
          <Route element={<Layout />}>
            <Route path="/" element={<Collections />} />
            <Route path="/collections/:id" element={<CollectionDetail />} />
            <Route path="/executions" element={<Executions />} />
            <Route path="/executions/batch" element={<BatchExecutionStatus />} />
            <Route path="/executions/:id" element={<ExecutionDetail />} />
            <Route path="/environments" element={<Environments />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </QueryClientProvider>
  );
}
