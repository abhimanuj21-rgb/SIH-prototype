import { Routes, Route, Navigate } from 'react-router-dom'
import CustomCursor from './components/CustomCursor.jsx'
import Layout from './components/Layout.jsx'
import LandingPage from './pages/LandingPage.jsx'
import DashboardPage from './pages/DashboardPage.jsx'
import ExplorerPage from './pages/ExplorerPage.jsx'
import IntelligencePage from './pages/IntelligencePage.jsx'
import HistoryPage from './pages/HistoryPage.jsx'
import ClimatePage from './pages/ClimatePage.jsx'
import DataRegistryPage from './pages/DataRegistryPage.jsx'
import DataQualityPage from './pages/DataQualityPage.jsx'
import OfficialDataAccessPage from './pages/OfficialDataAccessPage.jsx'

export default function App() {
  return (
    <>
      <CustomCursor />
      <Routes>
        <Route path="/" element={<LandingPage />} />
        <Route path="/app" element={<Layout />}>
          <Route index element={<Navigate to="/app/dashboard" replace />} />
          <Route path="dashboard" element={<DashboardPage />} />
          <Route path="explorer" element={<ExplorerPage />} />
          <Route path="intelligence" element={<IntelligencePage />} />
          <Route path="history" element={<HistoryPage />} />
          <Route path="climate" element={<ClimatePage />} />
          <Route path="data-registry" element={<DataRegistryPage />} />
          <Route path="data-quality" element={<DataQualityPage />} />
          <Route path="official-data-access" element={<OfficialDataAccessPage />} />
        </Route>
        <Route path="*" element={<Navigate to="/" replace />} />
      </Routes>
    </>
  )
}
