import { makeStyles } from '@mui/styles'

const useStyles = makeStyles({
  root: {
    width: 'min(92vw, 345px)'
  },
  sceneTitle: {
    fontSize: '1.1rem',
    whiteSpace: 'nowrap',
    overflow: 'hidden',
    textOverflow: 'ellipsis'
  },
  '@media (max-width: 580px)': {
    root: {
      width: '95vw'
    },
    sceneTitle: {
      fontSize: '1rem',
      cursor: 'default'
    }
  },
  media: {
    height: 140
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
  }
})

export default useStyles
