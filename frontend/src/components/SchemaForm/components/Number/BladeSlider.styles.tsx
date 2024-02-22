import { makeStyles } from '@mui/styles'

const useStyles = makeStyles(() => ({
  input: {
    marginLeft: '1rem',
    // backgroundColor: 'rgb(57, 57, 61)',
    paddingLeft: '0.5rem',
    borderRadius: '5px',
    paddingTop: '3px'
  },
  wrapper: {
    // minWidth: '220px',
    width: '49%',
    padding: '16px 1.2rem 6px 1.2rem',
    // border: '1px solid',
    // borderColor: theme.palette.divider,
    borderRadius: '10px',
    position: 'relative',
    display: 'flex',
    margin: '0.5rem 0',
    '@media (max-width: 580px)': {
      width: '100% !important'
    },
    '& > label': {
      top: '-0.75rem',
      display: 'flex',
      alignItems: 'center',
      left: '1rem',
      padding: '0 0.3rem',
      position: 'absolute',
      fontVariant: 'all-small-caps',
      fontSize: '0.9rem',
      letterSpacing: '0.1rem',
      boxSizing: 'border-box'
    },
    '& .sortable-handler': {
      touchAction: 'none'
    }
  }
}))

export default useStyles
