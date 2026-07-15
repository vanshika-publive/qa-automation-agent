import { Spinner } from './Spinner';

export function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-64px)]">
      <Spinner />
    </div>
  );
}
