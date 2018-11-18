import {
    drawerWidth
  } from "frontend/assets/jss/style.jsx";
  
  const appStyle = theme => ({
    root: {
      overflow: 'hidden',
      display: 'flex',
      width: '100%',
      position: 'absolute',
      bottom: '0',
      top: '0'
    },
    content: {
      flexGrow: 1,
      backgroundColor: theme.palette.background.default,
      padding: theme.spacing.unit * 3,
      minWidth: 200,
    },
    toolbar: theme.mixins.toolbar,
  });
  
  export default appStyle;
