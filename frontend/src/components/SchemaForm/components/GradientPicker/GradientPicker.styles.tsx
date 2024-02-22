import { makeStyles } from '@mui/styles'

const useStyles = makeStyles(() => ({
  paper: {
    border: '1px solid',
    borderRadius: 10,
    display: 'flex',
    flexWrap: 'wrap',
    maxWidth: '308px',
    overflow: 'auto',
    '& .gradient-result': {
      display: 'none'
    },
    '& .input_rgba': {
      display: 'none'
    },
    '&.show_hex .input_rgba': {
      display: 'block'
    },
    '&.show_hex .input_rgba .input_rgba-wrap .input_rgba-hex .input_rgba-hex-label':
      {
        color: '#eee',
        paddingTop: '1px'
      },
    '&.show_hex .input_rgba .input_rgba-wrap .input_rgba-hex input': {
      backgroundColor: '#333',
      color: '#eee',
      boxShadow: 'none',
      border: '1px solid #999'
    },
    '& .gradient-interaction': {
      order: -1,
      marginBottom: '1rem'
    },
    '& .colorpicker': {
      display: 'flex',
      flexDirection: 'column'
    },
    '& .color-picker-panel, & .popup_tabs-header, & .popup_tabs, & .colorpicker, & .colorpicker .color-picker-panel, & .popup_tabs-header .popup_tabs-header-label-active':
      {
        backgroundColor: 'transparent'
      },
    '& .popup_tabs-body': {
      paddingBottom: 4
    }
  },
  addButton: {
    width: 69,
    height: 30,
    borderRadius: 4,
    border: '1px solid #999',
    display: 'flex',
    justifyContent: 'center',
    alignItems: 'center',
    fontSize: 24,
    margin: '0 auto',
    cursor: 'pointer',
    '&:hover': {
      borderColor: '#fff'
    }
  },
  picker: {
    height: '30px',
    margin: '15px 10px 10px 10px',
    borderRadius: '10px',
    cursor: 'pointer',
    border: '1px solid #fff'
  },
  wrapper: {
    border: '1px solid rgba(255, 255, 255, 0.1)',
    borderRadius: '10px',
    position: 'relative',
    width: '100%',
    minWidth: '230px',
    margin: '0.5rem 0',
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
    }
  }
}))

export default useStyles
