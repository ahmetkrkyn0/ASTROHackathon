function joinClasses(...classes) {
  return classes.filter(Boolean).join(" ");
}

export default function PanelCard({
  title,
  description,
  actions,
  children,
  className = "",
  contentClassName = "",
}) {
  return (
    <section
      className={joinClasses(
        "rounded-2xl border border-slate-200 bg-white shadow-sm",
        className,
      )}
    >
      {(title || description || actions) && (
        <header className="flex flex-col gap-3 border-b border-slate-100 px-5 py-4 sm:flex-row sm:items-start sm:justify-between">
          <div>
            {title ? <h2 className="text-sm font-semibold text-slate-900">{title}</h2> : null}
            {description ? <p className="mt-1 text-sm text-slate-500">{description}</p> : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </header>
      )}

      <div className={joinClasses("px-5 py-4", contentClassName)}>{children}</div>
    </section>
  );
}
