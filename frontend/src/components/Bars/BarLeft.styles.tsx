import { makeStyles } from '@mui/styles'
import isElectron from 'is-electron'
import { drawerWidth } from '../../utils/helpers'
import blademod from '../../assets/blademod.svg'

const useStyles = makeStyles(() => ({
  '@global': {
    '*::-webkit-scrollbar': {
      backgroundColor: '#ffffff30',
      width: '8px',
      borderRadius: '8px'
    },
    '*::-webkit-scrollbar-track': {
      backgroundColor: '#00000060',
      borderRadius: '8px'
    },
    '*::-webkit-scrollbar-thumb': {
      backgroundColor: '#555555',
      borderRadius: '8px'
    },
    '*::-webkit-scrollbar-button': {
      display: 'none'
    }
  },
  drawer: {
    width: drawerWidth,
    flexShrink: 0
    // backgroundColor: theme.palette.background.default,
  },
  drawerPaper: {
    width: drawerWidth,
    overflowX: 'hidden',
    paddingTop: isElectron() ? '30px' : 0
  },
  drawerHeader: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  logo: {
    position: 'relative',
    padding: '0 0 0 5px',
    zIndex: 4
  },
  logoLink: {
    display: 'block',
    fontSize: '18px',
    textAlign: 'left',
    fontWeight: 400,
    lineHeight: '30px',
    textDecoration: 'none',
    backgroundColor: 'transparent',
    '&,&:hover': {
      color: '#FFFFFF'
    }
  },
  logoImage: {
    width: '30px',
    display: 'inline-block',
    maxHeight: '30px',
    marginRight: '15px',

    '& img': {
      width: '35px',
      marginTop: '-2px',
      // position: 'absolute',
      // verticalAlign: 'middle',
      border: '0'
    }
  },
  devbadge: {
    backgroundImage: `url(${blademod})`,
    color: '#fff',
    borderRadius: isElectron() ? 0 : '15px',
    width: '150px',
    padding: '5px 15px',
    backgroundSize: isElectron() ? '270px' : '230px',
    height: '20px',
    backgroundRepeat: 'no-repeat',
    textAlign: 'right',
    backgroundPosition: isElectron() ? '-66px 50%' : '-40px 50%',
    transform: 'scale(0.9)',
    marginRight: '-15px',
    transformOrigin: 'left center'
  }
}))
export default useStyles
