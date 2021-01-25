// Icons
import Dashboard from '@material-ui/icons/Dashboard';
import List from '@material-ui/icons/List';
import Settings from '@material-ui/icons/Settings';
import Tune from '@material-ui/icons/Tune';
import SaveAltIcon from '@material-ui/icons/SaveAlt';
import BuildIcon from '@material-ui/icons/Build';
import DeviceHubIcon from '@material-ui/icons/DeviceHub';
import PowerIcon from '@material-ui/icons/Power';
import LockOpenIcon from '@material-ui/icons/LockOpen';
import TvIcon from '@material-ui/icons/Tv';

// Components and Views
import DashboardView from '../views/Dashboard';
import DevicesView from '../views/Devices';
import ScenesView from '../views/Scenes';
import DeviceView from '../views/Device';
import DisplayView from '../views/Display';
import VirtualsView from '../views/Virtuals';
import DisplaysView from '../views/Displays';
import IntegrationsView from '../views/Integrations';
import AdvancedView from '../views/Advanced';
import SettingsView from '../views/Settings';
import DeveloperView from '../views/Developer';

const virtuals =
    parseInt(window.localStorage.getItem('BladeMod')) > 1
        ? {
              path: '/virtuals',
              sidebarName: 'Virtual Strips',
              navbarName: 'Virtual Strips',
              icon: DeviceHubIcon,
              component: VirtualsView,
          }
        : {
              path: '/virtuals',
              navbarName: 'Virtual Strips',
              icon: DeviceHubIcon,
              component: VirtualsView,
          };
const displays =
    parseInt(window.localStorage.getItem('BladeMod')) > 1
        ? {
              path: '/displays',
              sidebarName: 'Display Management',
              navbarName: 'Displays',
              icon: TvIcon,
              component: DisplaysView,
          }
        : {
              path: '/displays',
              navbarName: 'Displays',
              icon: TvIcon,
              component: DisplaysView,
          };
const integrations =
    parseInt(window.localStorage.getItem('BladeMod')) > 1
        ? {
              path: '/integrations',
              sidebarName: 'Integrations',
              navbarName: 'Integrations',
              icon: PowerIcon,
              component: IntegrationsView,
          }
        : {
              path: '/integrations',
              navbarName: 'Integrations',
              icon: PowerIcon,
              component: IntegrationsView,
          };
const advanced =
    parseInt(window.localStorage.getItem('BladeMod')) > 0
        ? {
              path: '/advanced',
              sidebarName: 'Advanced',
              navbarName: 'Advanced',
              icon: LockOpenIcon,
              component: AdvancedView,
          }
        : {
              path: '/advanced',
              navbarName: 'Advanced',
              icon: LockOpenIcon,
              component: AdvancedView,
          };
const viewRoutes = [
    {
        path: '/dashboard',
        sidebarName: 'Dashboard',
        navbarName: 'Dashboard',
        icon: Dashboard,
        component: DashboardView,
    },
    {
        path: '/displays/:displayId',
        navbarName: 'Displays',
        sidebarName: 'Displays',
        icon: List,
        component: DisplayView,
    },
    {
        path: '/devices/:deviceId',
        navbarName: 'Devices',
        sidebarName: 'Devices',
        icon: List,
        component: DeviceView,
    },
    {
        path: '/scenes',
        sidebarName: 'Scenes Management',
        navbarName: 'Scenes Management',
        icon: SaveAltIcon,
        component: ScenesView,
    },
    {
        path: '/devices',
        sidebarName: 'Device Management',
        navbarName: 'Device Management',
        icon: Settings,
        component: DevicesView,
    },
    displays,
    integrations,
    virtuals,
    {
        path: '/settings',
        sidebarName: 'Settings',
        navbarName: 'Settings',
        icon: BuildIcon,
        component: SettingsView,
    },
    advanced,
    {
        path: '/developer/:graphString',
        navbarName: 'Developer',
        component: DeveloperView,
    },
    {
        path: '/developer/melbank',
        sidebarName: 'Developer',
        navbarName: 'Developer',
        icon: Tune,
        component: DeveloperView,
    },
    { redirect: true, path: '/', to: '/dashboard', navbarName: 'Redirect' },
];

export default viewRoutes;
