import {
    drawerWidth
  } from "frontend/assets/jss/style.jsx";
  
  
const headerStyle = theme => ({
    appBar: {
      backgroundColor: "transparent",
      boxShadow: "none",
      position: 'absolute',
      marginLeft: drawerWidth,
      [theme.breakpoints.up('md')]: {
        width: `calc(100% - ${drawerWidth}px)`,
      },
    },
    
    flex: {
      flex: 1,
      fontSize: 18,
      fontWeight: 300,
    }
  });
  
  export default headerStyle;
  