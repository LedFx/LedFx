import { makeStyles } from '@mui/styles'

const useSegmentStyles = makeStyles(() => ({
  segmentsWrapper: {
    display: 'flex',
    borderBottom: '1px dashed #aaa',
    justifyContent: 'space-between',
    alignItems: 'center',
    padding: '0.5rem 0'
  },
  segmentsColOrder: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  segmentsButtonUp: {
    borderTopRightRadius: 0,
    borderBottomRightRadius: 0,
    minWidth: '50px'
  },
  segmentsButtonDown: {
    borderTopLeftRadius: 0,
    borderBottomLeftRadius: 0,
    minWidth: '50px',
    marginRight: '1rem'
  },
  segmentsColPixelSlider: {
    flex: '0 1 70%'
  },
  segmentsColActions: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'center'
  },
  '@media (max-width: 600px)': {
    segmentsColPixelSlider: {
      order: 3,
      width: 'calc(100% - 2rem)',
      margin: '2rem auto 0 auto'
    },

    segmentsWrapper: {
      flexDirection: 'column',
      alignItems: 'flex-start'
    },
    segmentsColActions: {
      position: 'absolute',
      right: '1rem'
    }
  }
}))

export default useSegmentStyles
