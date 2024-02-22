import { makeStyles } from '@mui/styles'

const useStyles = makeStyles(() => ({
  FormRow: {
    display: 'flex',
    flexDirection: 'row',
    border: '1px solid',
    borderRadius: '10px',
    margin: '0 0 0.5rem',
    '@media (max-width: 580px)': {
      flexDirection: 'column'
    }
  },
  FormLabel: {
    marginLeft: '1rem',
    paddingTop: '0.5rem',
    '@media (max-width: 580px)': {
      display: 'none'
    }
  },
  FormSelect: {
    flexGrow: 1,
    marginLeft: '1rem',
    paddingTop: '0.5rem',
    '&:before, &:after': {
      display: 'none'
    },
    '& > .MuiSelect-select:focus': {
      backgroundColor: 'unset'
    }
  },
  FormListHeaders: {
    pointerEvents: 'none',
    color: '#fff'
  },
  FormListItem: {
    paddingLeft: '2rem'
  },
  FormToggleWrapper: {
    padding: '5px 0',
    '@media (max-width: 580px)': {
      order: -1
    }
  },

  FormToggle: {
    fontSize: '0.64rem',
    '@media (max-width: 580px)': {
      flexGrow: 1
    }
  }
}))

export default useStyles
