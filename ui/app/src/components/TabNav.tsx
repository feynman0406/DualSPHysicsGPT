import './TabNav.css';

interface TabOption<T extends string> {
  id: T;
  label: string;
  badge?: string;
}

interface TabNavProps<T extends string> {
  tabs: TabOption<T>[];
  active: T;
  onChange: (id: T) => void;
}

const TabNav = <T extends string>({ tabs, active, onChange }: TabNavProps<T>) => {
  return (
    <div className="tab-nav" role="tablist">
      {tabs.map(tab => (
        <button
          type="button"
          key={tab.id}
          role="tab"
          aria-selected={active === tab.id}
          className={active === tab.id ? 'active' : undefined}
          onClick={() => onChange(tab.id)}
        >
          {tab.label}
          {tab.badge && <span className="badge">{tab.badge}</span>}
        </button>
      ))}
    </div>
  );
};

export default TabNav;
