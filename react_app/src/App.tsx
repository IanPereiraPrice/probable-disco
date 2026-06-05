import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import { Sidebar } from '@/components/layout/Sidebar'
import { PageLayout } from '@/components/layout/PageLayout'
import { CharacterSettings } from '@/pages/CharacterSettings'
import { CharacterStats } from '@/pages/CharacterStats'
import { Equipment } from '@/pages/Equipment'
import { HeroPower } from '@/pages/HeroPower'
import { Artifacts } from '@/pages/Artifacts'
import { Companions } from '@/pages/Companions'
import { MapleRank } from '@/pages/MapleRank'
import { Weapons } from '@/pages/Weapons'
import { DamageCalculator } from '@/pages/DamageCalculator'
import { SkillBreakdown } from '@/pages/SkillBreakdown'
import { CooldownAnalyzer } from '@/pages/CooldownAnalyzer'

export default function App() {
  return (
    <BrowserRouter>
      <div className="flex h-screen bg-slate-950 overflow-hidden">
        <Sidebar />
        <main className="flex-1 overflow-y-auto">
          <Routes>
            <Route path="/" element={<Navigate to="/character-settings" replace />} />
            <Route path="/character-settings" element={<PageLayout title="Character Settings"><CharacterSettings /></PageLayout>} />
            <Route path="/character-stats"    element={<PageLayout title="Character Stats"><CharacterStats /></PageLayout>} />
            <Route path="/equipment"          element={<PageLayout title="Equipment"><Equipment /></PageLayout>} />
            <Route path="/hero-power"         element={<PageLayout title="Hero Power"><HeroPower /></PageLayout>} />
            <Route path="/artifacts"          element={<PageLayout title="Artifacts"><Artifacts /></PageLayout>} />
            <Route path="/companions"         element={<PageLayout title="Companions"><Companions /></PageLayout>} />
            <Route path="/maple-rank"         element={<PageLayout title="Maple Rank"><MapleRank /></PageLayout>} />
            <Route path="/weapons"            element={<PageLayout title="Weapons"><Weapons /></PageLayout>} />
            <Route path="/damage-calculator"  element={<PageLayout title="Damage Calculator"><DamageCalculator /></PageLayout>} />
            <Route path="/skill-breakdown"    element={<PageLayout title="Skill Breakdown"><SkillBreakdown /></PageLayout>} />
            <Route path="/cooldown-analyzer"  element={<PageLayout title="Cooldown Analyzer"><CooldownAnalyzer /></PageLayout>} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
