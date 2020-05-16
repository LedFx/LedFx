// Icons
import Dashboard from "@material-ui/icons/Dashboard";
import List from "@material-ui/icons/List";
import Settings from "@material-ui/icons/Settings";
import Tune from "@material-ui/icons/Tune";
import SaveAltIcon from '@material-ui/icons/SaveAlt';
import BuildIcon from '@material-ui/icons/Build';

// Components and Views
import DashboardView from "../views/Dashboard/Dashboard";
import DevicesView from "../views/Devices/Devices";
import PresetsView from "../views/Presets/Presets";
import DeviceView from "../views/Device/Device";
import SettingsView from "../views/Settings/Settings";
import DeveloperView from "../views/Developer/Developer";

const viewRoutes = [
  {
    path: "/dashboard",
    sidebarName: "Dashboard",
    navbarName: "Dashboard",
    icon: Dashboard,
    component: DashboardView
  },
  {
    path: "/devices/:device_id",
    navbarName: "Devices",
    sidebarName: "Devices",
    icon: List,
    component: DeviceView,
  },
  {
    path: "/presets",
    sidebarName: "Presets Management",
    navbarName: "Presets Management",
    icon: SaveAltIcon,
    component: PresetsView,
  },
  {
    path: "/devices",
    sidebarName: "Device Management",
    navbarName: "Device Management",
    icon: Settings,
    component: DevicesView
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

