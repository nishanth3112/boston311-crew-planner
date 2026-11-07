import '@fontsource/overpass/400.css'
import '@fontsource/overpass/600.css'
import '@fontsource/overpass/700.css'
import '@fontsource/atkinson-hyperlegible/400.css'
import '@fontsource/atkinson-hyperlegible/700.css'
import './index.css'

import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import { createBrowserRouter } from 'react-router'
import { RouterProvider } from 'react-router/dom'
import App from './App.tsx'
import Ask from './pages/Ask.tsx'
import CrewPlan from './pages/CrewPlan.tsx'
import Intake from './pages/Intake.tsx'
import Scenarios from './pages/Scenarios.tsx'

const router = createBrowserRouter([
  {
    element: <App />,
    children: [
      { path: '/', element: <Intake /> },
      { path: '/plan', element: <CrewPlan /> },
      { path: '/scenarios', element: <Scenarios /> },
      { path: '/ask', element: <Ask /> },
    ],
  },
])

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <QueryClientProvider client={new QueryClient()}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  </StrictMode>,
)
