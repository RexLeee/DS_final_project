import { createBrowserRouter, RouterProvider } from 'react-router-dom';
import Layout from './components/Layout';
import Campaigns from './pages/Campaigns';
import CampaignDetail from './pages/CampaignDetail';
import Login from './pages/Login';
import Register from './pages/Register';
import CreateCampaign from './pages/admin/CreateCampaign';

const router = createBrowserRouter([
  {
    path: '/',
    element: <Layout />,
    children: [
      { index: true, element: <Campaigns /> },
      { path: 'login', element: <Login /> },
      { path: 'register', element: <Register /> },
      { path: 'campaigns/:id', element: <CampaignDetail /> },
      {
        path: 'admin',
        children: [
          { path: 'create', element: <CreateCampaign /> },
        ],
      },
    ],
  },
]);

export default function App() {
  return <RouterProvider router={router} />;
}
