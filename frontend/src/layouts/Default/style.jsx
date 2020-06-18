import { drawerWidth } from 'assets/jss/style';

const appStyle = theme => ({
    root: {
        overflow: 'hidden',
        display: 'flex',
        width: '100%',
        height: '100%',
    },
    content: {
        flexGrow: 1,
        backgroundColor: theme.palette.background.default,
        padding: theme.spacing(3),
        minWidth: 200,
        [theme.breakpoints.up('md')]: {
            marginLeft: drawerWidth,
        },
        overflowY: 'auto',
    },
    toolbar: theme.mixins.toolbar,
});

export default appStyle;
