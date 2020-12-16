// Icons
import Dashboard from "@material-ui/icons/Dashboard";
import List from "@material-ui/icons/List";
import Settings from "@material-ui/icons/Settings";
import Tune from "@material-ui/icons/Tune";
import SaveAltIcon from '@material-ui/icons/SaveAlt';
import BuildIcon from '@material-ui/icons/Build';
// import DeviceHubIcon from '@material-ui/icons/DeviceHub';

// Components and Views
import DashboardView from "../views/Dashboard";
import DevicesView from "../views/Devices";
import ScenesView from "../views/Scenes";
import DeviceView from "../views/Device";
import VirtualsView from "../views/Virtuals";
import SettingsView from "../views/Settings";
import DeveloperView from "../views/Developer";

const viewRoutes = [
  {
    path: "/dashboard",
    sidebarName: "Dashboard",
    navbarName: "Dashboard",
    icon: Dashboard,
    component: DashboardView
  },
  {
    path: "/devices/:deviceId",
    navbarName: "Devices",
    sidebarName: "Devices",
    icon: List,
    component: DeviceView,
  },
  {
    path: "/scenes",
    sidebarName: "Scenes Management",
    navbarName: "Scenes Management",
    icon: SaveAltIcon,
    component: ScenesView,
  },
  {
    path: "/devices",
    sidebarName: "Device Management",
    navbarName: "Device Management",
    icon: Settings,
    component: DevicesView
  },
  {
    path: "/virtuals",
    // sidebarName: "Virtual Strips",
    // navbarName: "Virtual Strips",
    // icon: DeviceHubIcon,
    component: VirtualsView
  },
  {
    path: "/settings",
    sidebarName: "Settings",
    navbarName: "Settings",
    icon: BuildIcon,
    component: SettingsView
  },
  {
    path: "/developer/:graphString",
    navbarName: "Developer",
    component: DeveloperView
  },
  {
    path: "/developer/melbank",
    sidebarName: "Developer",
    navbarName: "Developer",
    icon: Tune,
    component: DeveloperView
  },
  { redirect: true, path: "/", to: "/dashboard", navbarName: "Redirect" }
];

export default viewRoutes;

