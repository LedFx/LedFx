import { makeStyles } from '@mui/styles'

const useStyles = makeStyles(() => ({
  Widget: {
    padding: 0,
    overflow: 'hidden',
    borderRadius: 16,
    width: 960,
    maxWidth: '100%',
    margin: '0',
    position: 'relative',
    zIndex: 1,
    backgroundColor: '#2229',
    backdropFilter: 'blur(40px)',
    '@media (max-width: 720px)': {
      '&&': {
        width: 400
      }
    },
    '&.small': {
      '&&': {
        width: 400
      }
    }
  }
}))

export const VolSliderStyles = {
  color: '#fff',
  '& .MuiSlider-track': {
    border: 'none'
  },
  '& .MuiSlider-thumb': {
    width: 16,
    height: 16,
    backgroundColor: '#fff',
    '&:before': {
      boxShadow: '0 4px 8px rgba(0,0,0,0.4)'
    },
    '&:hover, &.Mui-focusVisible, &.Mui-active': {
      boxShadow: 'none'
    }
  }
}

export default useStyles
