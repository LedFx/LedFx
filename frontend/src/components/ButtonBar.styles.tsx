import { makeStyles } from '@mui/styles'

const useStyles = makeStyles(() => ({
  buttonBar: {
    position: 'relative',
    bottom: 0,
    left: 0,
    right: 0,
    paddingTop: '0.4rem',
    paddingBottom: '0.4rem',
    textAlign: 'center',
    color: '#FFFFFF',
    '& > a': {
      margin: '0 5px'
    }
  }
}))

export default useStyles
