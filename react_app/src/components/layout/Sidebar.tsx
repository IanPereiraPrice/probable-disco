import { NavLink } from 'react-router-dom'
import {
  User,
  Shield,
  Zap,
  BarChart2,
  Clock,
  Swords,
  Activity,
  Flame,
  Star,
  Users,
  Trophy,
  Sword,
} from 'lucide-react'

const NAV_GROUPS = [
  {
    label: 'Character',
    items: [
      { to: '/character-settings', icon: User,     label: 'Character' },
      { to: '/character-stats',    icon: Activity,  label: 'Stats' },
      { to: '/maple-rank',         icon: Trophy,    label: 'Maple Rank' },
    ],
  },
  {
    label: 'Gear',
    items: [
      { to: '/equipment',          icon: Shield,    label: 'Equipment' },
      { to: '/weapons',            icon: Sword,     label: 'Weapons' },
      { to: '/artifacts',          icon: Star,      label: 'Artifacts' },
    ],
  },
  {
    label: 'Power',
    items: [
      { to: '/hero-power',         icon: Flame,     label: 'Hero Power' },
      { to: '/companions',         icon: Users,     label: 'Companions' },
    ],
  },
  {
    label: 'Analysis',
    items: [
      { to: '/damage-calculator',  icon: Swords,    label: 'Damage Calc' },
      { to: '/skill-breakdown',    icon: BarChart2, label: 'Skills' },
      { to: '/cooldown-analyzer',  icon: Clock,     label: 'Cooldowns' },
    ],
  },
]

export function Sidebar() {
  return (
    <aside className="w-48 flex-shrink-0 bg-slate-900 border-r border-slate-800 flex flex-col overflow-y-auto">
      {/* Logo */}
      <div className="px-4 py-5 border-b border-slate-800 shrink-0">
        <div className="flex items-center gap-2">
          <Zap className="w-5 h-5 text-orange-400" />
          <span className="font-bold text-sm text-slate-100">Maple Idle</span>
        </div>
        <p className="text-xs text-slate-500 mt-0.5">DPS Calculator</p>
      </div>

      {/* Navigation */}
      <nav className="flex-1 px-2 py-3 space-y-4">
        {NAV_GROUPS.map(({ label, items }) => (
          <div key={label}>
            <p className="px-3 mb-1 text-xs font-semibold text-slate-600 uppercase tracking-wider">{label}</p>
            <div className="space-y-0.5">
              {items.map(({ to, icon: Icon, label: itemLabel }) => (
                <NavLink
                  key={to}
                  to={to}
                  className={({ isActive }) =>
                    `flex items-center gap-3 px-3 py-2 rounded-lg text-sm transition-colors ${
                      isActive
                        ? 'bg-orange-500/15 text-orange-400 font-medium'
                        : 'text-slate-400 hover:text-slate-200 hover:bg-slate-800'
                    }`
                  }
                >
                  <Icon className="w-4 h-4 flex-shrink-0" />
                  {itemLabel}
                </NavLink>
              ))}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  )
}
