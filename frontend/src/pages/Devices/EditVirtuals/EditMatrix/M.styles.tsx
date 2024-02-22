import { makeStyles } from '@mui/styles'

const useStyles = makeStyles(() => ({
  gridCell: {
    cursor: 'copy',
    border: '1px solid #666',
    // background: '#111',
    width: 100,
    height: 100,
    '&:hover': {
      // background: '#999'
    }
  },
  gridCellContainer: {
    background: '#111',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center'
  },
  gridCellInner: {
    display: 'flex',
    flexWrap: 'wrap',
    height: '100%',
    width: '100%'
  },
  pixel: {
    display: 'flex',
    flexDirection: 'column',
    justifyContent: 'space-between',
    alignItems: 'center',
    height: '98px',
    background: 'transparent',
    width: '98px',
    border: '5px solid #111',
    boxSizing: 'border-box',
    padding: '8px',
    borderRadius: '10px'
  },
  centered: {
    display: 'flex',
    width: '100%',
    justifyContent: 'space-between'
  }
}))
export default useStyles
