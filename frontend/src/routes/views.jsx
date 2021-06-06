// Icons
import Dashboard from '@material-ui/icons/Dashboard';
import List from '@material-ui/icons/List';
import Settings from '@material-ui/icons/Settings';
import Tune from '@material-ui/icons/Tune';
import SaveAltIcon from '@material-ui/icons/SaveAlt';
import BuildIcon from '@material-ui/icons/Build';
import PowerIcon from '@material-ui/icons/Power';


// Components and Views
import BladeboardDnDView from '../views/Dashboard/BladeBoardDnD';
import DevicesView from '../views/Devices';
import ScenesView from '../views/Scenes';
import DisplayView from '../views/Display';
import IntegrationsView from '../views/Integrations';
import AdvancedView from '../views/Advanced';
import DeveloperView from '../views/Developer';

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

const viewRoutes = [
    {
        path: '/dashboard',
        sidebarName: 'Dashboard',
        navbarName: 'Dashboard',
        icon: Dashboard,
        component: BladeboardDnDView,
    },
    {
        path: '/displays/:displayId',
        navbarName: 'Displays',
        sidebarName: 'Displays',
        icon: List,
        component: DisplayView,
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
    integrations,
    {
        path: '/settings',
        sidebarName: 'Settings',
        navbarName: 'Settings',
        icon: BuildIcon,
        component: AdvancedView,
    },
    {
        path: '/developer/:graphString',
        sidebarName: 'Developer',
        navbarName: 'Developer',
        icon: Tune,
        component: DeveloperView,
    },
    { redirect: true, path: '/', to: '/dashboard', navbarName: 'Redirect' },
];

export default viewRoutes;
