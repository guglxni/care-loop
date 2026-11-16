import { BrowserRouter, Navigate, Route, Routes } from "react-router-dom"
import { AppShell } from "@/components/layout/AppShell"
import { DoseTrackerProvider } from "@/state/dose-tracker"
import { BloodPressurePage } from "@/pages/blood-pressure/BloodPressurePage"
import { CalendarPage } from "@/pages/calendar/CalendarPage"
import { CompanionPage } from "@/pages/companion/CompanionPage"
import { DashboardPage } from "@/pages/dashboard/DashboardPage"
import { DemoPage } from "@/pages/demo/DemoPage"
import { GlucosePage } from "@/pages/glucose/GlucosePage"
import { IngestPage } from "@/pages/ingest/IngestPage"
import { MedicationsPage } from "@/pages/medications/MedicationsPage"
import { ProfilePage } from "@/pages/profile/ProfilePage"
import { ReportsPage } from "@/pages/reports/ReportsPage"
import { ShowcasePage } from "@/pages/showcase/ShowcasePage"

export default function App() {
  return (
    <BrowserRouter>
      <DoseTrackerProvider>
        <Routes>
          <Route element={<AppShell />}>
            <Route path="/" element={<DashboardPage />} />
            <Route path="/profile" element={<ProfilePage />} />
            <Route path="/glucose" element={<GlucosePage />} />
            <Route path="/blood-pressure" element={<BloodPressurePage />} />
            <Route path="/ingest" element={<IngestPage />} />
            <Route path="/medications" element={<MedicationsPage />} />
            <Route path="/calendar" element={<CalendarPage />} />
            <Route path="/reports" element={<ReportsPage />} />
            <Route path="/companion" element={<CompanionPage />} />
            <Route path="/demo" element={<DemoPage />} />
            <Route path="/showcase" element={<ShowcasePage />} />
            <Route path="*" element={<Navigate to="/" replace />} />
          </Route>
        </Routes>
      </DoseTrackerProvider>
    </BrowserRouter>
  )
}
