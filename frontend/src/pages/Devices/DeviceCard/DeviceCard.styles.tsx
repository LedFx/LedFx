import { makeStyles } from '@mui/styles'

const useStyle = makeStyles(() => ({
  virtualCardPortraitW: {
    margin: '0.5rem',
    display: 'flex',
    alignItems: 'flex-start',
    flexDirection: 'column',
    minWidth: '230px',
    maxWidth: '400px',
    width: '100%',
    height: '100%',
    position: 'relative',
    borderRadius: 10,
    borderColor: 'transparent',
    textDecoration: 'none',
    '@media (max-width: 410px)': {
      margin: '0.25rem 0'
    }
  },
  virtualCardPortrait: {
    padding: '1rem 0.7rem 0.7rem 0.7rem',
    display: 'flex',
    alignItems: 'flex-start',
    flexDirection: 'column',
    minWidth: '230px',
    maxWidth: '400px',
    width: '100%',
    height: '100%',
    position: 'relative',
    borderRadius: 10,
    borderColor: 'transparent'
  },
  virtualIconWrapper: {
    width: '50px',
    height: '55px',
    marginRight: '0.5rem'
  },
  virtualIcon: {
    marginBottom: '4px',
    marginRight: '0.5rem',
    fontSize: '50px',
    position: 'absolute',
    transformOrigin: 'top left',
    '&.graphs': {
      transformOrigin: 'center left'
    },
    transition: 'transform 0.3s ease-in-out',
    transitionDelay: '0s',
    '&.extended': {
      transform: 'scale(1.7) translateY(-4px);',
      transformOrigin: 'top left',
      transition: 'transform 0.3s ease-in-out',
      transitionDelay: '0s'
    },
    '&.extended.graphs': {
      transform: 'scale(1.25)',
      transformOrigin: 'center left',
      transition: 'transform 0.3s ease-in-out',
      transitionDelay: '0s'
    },
    '& svg': {
      transform: 'unset',
      width: '100%',
      marginTop: '3px',
      height: '100%'
    }
  },

  virtualCardContainer: {
    display: 'flex',
    alignItems: 'center',
    width: '100%',
    height: '100%',
    minHeight: '73px',
    padding: '0 0.3rem',
    justifyContent: 'space-between',
    flexDirection: 'row'
  },

  virtualSubline: {
    padding: '0 0.5rem'
  },

  iconMedia: {
    height: 140,
    display: 'flex',
    alignItems: 'center',
    margin: '0 auto',
    fontSize: 100,
    '& > span:before': {
      position: 'relative'
    }
  },
  editButton: {
    // marginLeft: theme.spacing(1),
    minWidth: 'unset'
  },
  editButtonMobile: {
    // marginLeft: theme.spacing(1),
    minWidth: 'unset',
    flexGrow: 1
  },
  buttonBarMobile: {
    width: '100%',
    height: '100%',
    textAlign: 'right'
  },
  buttonBarMobileWrapper: {
    height: 110,
    display: 'flex',
    margin: 0,
    padding: '0.5rem 80px 0.5rem 0.5rem',
    background: 'rgba(0,0,0,0.93)',
    color: '#fff',
    '& > div, & > button': {
      flexGrow: 1,
      flexBasis: '30%'
    },
    '&.extended.graphs': {
      height: 'auto',
      paddingTop: 0,
      '& button': {
        fontSize: 'smaller'
      }
    }
  },
  pixelbar: {
    opacity: 1,
    transitionDuration: '0s',
    width: '100%'
  },
  pixelbarOut: {
    opacity: 0.2,
    transition: 'opacity',
    transitionDuration: '1s'
  }
}))

export default useStyle
