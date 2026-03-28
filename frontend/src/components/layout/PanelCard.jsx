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
    <section className={joinClasses("mission-surface", className)}>
      {(title || description || actions) && (
        <header className="flex flex-col gap-3 px-5 py-5 sm:flex-row sm:items-start sm:justify-between">
          <div>
            {title ? <p className="mission-label">{title}</p> : null}
            {description ? <p className="mt-2 text-sm leading-6 text-slate-500">{description}</p> : null}
          </div>
          {actions ? <div className="shrink-0">{actions}</div> : null}
        </header>
      )}

      <div className={joinClasses("px-5 pb-5", contentClassName)}>{children}</div>
    </section>
  );
}
