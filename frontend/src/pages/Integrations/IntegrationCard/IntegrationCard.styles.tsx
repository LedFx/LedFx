import { makeStyles } from '@mui/styles'

const useIntegrationCardStyles = makeStyles(() => ({
  integrationCardPortrait: {
    padding: '1rem',
    margin: '0.5rem',
    display: 'flex',
    alignItems: 'flex-start',
    flexDirection: 'column',
    width: '360px',
    justifyContent: 'space-between',
    '@media (max-width: 580px)': {
      maxWidth: '97vw',
      margin: '0 auto',
      height: 'unset'
    }
  },
  integrationLink: {
    flexGrow: 0,
    padding: '0 0.5rem',
    textDecoration: 'none',
    fontSize: 'large',
    color: 'inherit'

    // '&:hover': {
    //   color: theme.palette.primary.main,
    // },
  },
  integrationIcon: {
    margingBottom: '4px',
    marginRight: '0.5rem',
    position: 'relative',
    fontSize: '50px'
  },
  integrationCardContainer: {
    display: 'flex',
    alignItems: 'center',
    flexDirection: 'column',
    width: '100%',
    height: '100%',
    justifyContent: 'space-between',
    '@media (max-width: 580px)': {
      flexDirection: 'row'
    }
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
    minWidth: 32,
    // marginLeft: theme.spacing(1),
    '@media (max-width: 580px)': {
      minWidth: 'unset'
    }
  },
  editButtonMobile: {
    minWidth: 32,
    // marginLeft: theme.spacing(1),
    '@media (max-width: 580px)': {
      minWidth: 'unset',
      flexGrow: 1
    }
  },
  buttonBar: {
    '@media (max-width: 580px)': {
      display: 'none'
    }
  },
  buttonBarMobile: {
    width: '100%',
    textAlign: 'right'
  },
  buttonBarMobileWrapper: {
    display: 'flex',
    margin: '0 -1rem -1rem -1rem',
    padding: '0.5rem 0.5rem 1.5rem 0.5rem',
    background: 'rgba(0,0,0,0.4)',
    '& > div, & > button': {
      flexGrow: 1,
      flexBasis: '30%'
    },
    '& > div > button': {
      width: '100%'
    }
  }
}))

export default useIntegrationCardStyles
