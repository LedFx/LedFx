import { makeStyles } from '@mui/styles'

const useTroubleshootStyles = makeStyles(() => ({
  appBar: {
    position: 'relative',
    marginBottom: '1rem'
    // background: theme.palette.background.default,
    // color: theme.palette.text.primary,
  },
  title: {
    // marginLeft: theme.spacing(2),
    flex: 1
  },
  row: {
    display: 'flex',
    justifyContent: 'space-between',
    minWidth: '20px'
  },
  segmentTitle: {
    display: 'flex',
    borderBottom: '1px dashed #aaa',
    justifyContent: 'center',
    alignItems: 'center',
    padding: '0.5rem 0',
    margin: '0 1rem'
  }
}))

export default useTroubleshootStyles
