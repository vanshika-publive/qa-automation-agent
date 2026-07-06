import { Spinner } from './Spinner';

/** Full-height centered spinner for a page/section that is still loading. */
export function PageLoader() {
  return (
    <div className="flex items-center justify-center min-h-[calc(100vh-64px)]">
      <Spinner />
    </div>
  );
}
