export default function PageShell({ topBar, children }) {
  return (
    <div className="min-h-screen bg-slate-100 text-slate-900">
      {topBar}
      <main className="mx-auto w-full max-w-7xl px-4 py-6 sm:px-6 lg:px-8">{children}</main>
    </div>
  );
}
