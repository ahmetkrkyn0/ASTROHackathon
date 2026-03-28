export default function PageShell({ topBar, children }) {
  return (
    <div className="relative min-h-screen overflow-hidden text-slate-900">
      <div className="pointer-events-none absolute inset-x-0 top-0 h-72 bg-gradient-to-b from-white/60 to-transparent" />
      {topBar}
      <main className="relative mx-auto w-full max-w-[1600px] px-4 py-6 sm:px-6 lg:px-8 xl:py-8">
        {children}
      </main>
    </div>
  );
}
