import {
    drawerWidth
  } from "frontend/assets/jss/style.jsx";
  
  const appStyle = theme => ({
    root: {
      overflow: 'hidden',
      position: 'relative',
      display: 'flex',
      width: '100%'
    },
    content: {
      flexGrow: 1,
      backgroundColor: theme.palette.background.default,
      padding: theme.spacing.unit * 3,
    },
    toolbar: theme.mixins.toolbar,
  });
  
  export default appStyle;
