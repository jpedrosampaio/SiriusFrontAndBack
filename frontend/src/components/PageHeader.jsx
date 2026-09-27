export default function PageHeader({ eyebrow, title, description, primaryAction, secondaryActions, badge }) {
  return <header className="sirius-page-header">
    <div>{eyebrow && <p className="sirius-eyebrow">{eyebrow}</p>}<div className="flex flex-wrap items-center gap-3"><h1>{title}</h1>{badge}</div>{description && <p className="sirius-page-description">{description}</p>}</div>
    {(primaryAction || secondaryActions) && <div className="flex flex-wrap items-center gap-2">{secondaryActions}{primaryAction}</div>}
  </header>;
}
