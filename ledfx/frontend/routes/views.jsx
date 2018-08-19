// Icons
import Dashboard from "@material-ui/icons/Dashboard";
import List from "@material-ui/icons/List";
import Tune from "@material-ui/icons/Tune";

// Components and Views
import DashboardView from "frontend/views/Dashboard/Dashboard.jsx";
import DevicesView from "frontend/views/Devices/Devices.jsx";
import DeviceView from "frontend/views/Device/Device.jsx";
import DeveloperView from "frontend/views/Developer/Developer.jsx";

const viewRoutes = [
  {
    path: "/dashboard",
    sidebarName: "Dashboard",
    navbarName: "Dashboard",
    icon: Dashboard,
    component: DashboardView
  },
  {
    path: "/devices",
    sidebarName: "Devices",
    navbarName: "Devices",
    icon: List,
    component: DevicesView
  },
  {
    path: "/developer",
    sidebarName: "Developer",
    navbarName: "Developer",
    icon: Tune,
    component: DeveloperView
  },
  {
    path: "/devices/:device_id",
    component: DeviceView,
    navbarName: "Devices",
  },
  { redirect: true, path: "/", to: "/dashboard", navbarName: "Redirect" }
];

export default viewRoutes;
