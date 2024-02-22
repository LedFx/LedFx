/* eslint-disable react/jsx-no-useless-fragment */
import { makeStyles, styled } from '@mui/styles'
import {
  Accordion,
  AccordionDetails,
  AccordionSummary,
  Button,
  Slider,
  Switch,
  Tooltip,
  Typography,
  useTheme
} from '@mui/material'
import { ExpandMore } from '@mui/icons-material'
// import { ChevronRight, ExpandMore } from '@mui/icons-material'
import useStore from '../../store/useStore'
import BladeIcon from '../../components/Icons/BladeIcon/BladeIcon'

export const useStyles = makeStyles(() => ({
  content: {
    display: 'flex',
    justifyContent: 'space-between',
    alignItems: 'flex-start',
    flexDirection: 'row',
    '&>div': {
      display: 'flex',
      flexWrap: 'wrap',
      justifyContent: 'space-between'
    }
  },
  settingsRow: {
    order: 'unset',
    width: '100%',
    justifyContent: 'space-between',
    display: 'flex',
    alignItems: 'center',
    height: 40,
    '&>label': {
      marginRight: '1rem'
    },
    '&.slider>label': {
      width: 150
    }
  },
  actionButton: {
    marginTop: '0.5rem',
    flexBasis: '49%',
    width: '100%',
    borderColor: '#444'
  },
  card: {
    maxWidth: '540px',
    margin: '1rem auto 0' // mobile
  },
  '@media (max-width: 580px)': {
    card: {
      maxWidth: '97vw',
      margin: '0 auto'
    }
  },
  audioCard: {
    '& > div > div:not(:last-child)': {
      '@media (max-width: 580px)': {
        width: '48% !important',
        minWidth: 'unset'
      }
    }
  }
}))

export const SettingsStylesSlider = styled(Slider)(({ theme }: any) => ({
  color: '#eeeeee',
  height: 2,
  padding: '15px 0',
  '& .MuiSlider-thumb': {
    height: 20,
    width: 20,
    backgroundColor: '#fff',
    boxShadow:
      '0 3px 1px rgba(0,0,0,0.1),0 4px 8px rgba(0,0,0,0.13),0 0 0 1px rgba(0,0,0,0.02)',
    '&:focus, &:hover, &.Mui-active': {
      boxShadow:
        '0 3px 1px rgba(0,0,0,0.1),0 4px 8px rgba(0,0,0,0.3),0 0 0 1px rgba(0,0,0,0.02)',
      // Reset on touch devices, it doesn't add specificity
      '@media (hover: none)': {
        boxShadow:
          '0 3px 1px rgba(0,0,0,0.1),0 4px 8px rgba(0,0,0,0.13),0 0 0 1px rgba(0,0,0,0.02)'
      }
    }
  },
  '& .MuiSliderValueLabel ': {
    fontSize: 12,
    fontWeight: 'normal',
    top: -6,
    backgroundColor: 'unset',
    color: theme.palette.text.primary,
    '&:before': {
      display: 'none'
    },
    '& *': {
      background: 'transparent',
      color: theme.palette.mode === 'dark' ? '#fff' : '#000'
    }
  },
  '& .MuiSlider-track': {
    border: 'none'
  },
  '& .MuiSlider-rail': {
    opacity: 0.5,
    backgroundColor: '#bfbfbf'
  },
  '& .MuiSlider-mark': {
    backgroundColor: '#bfbfbf',
    height: 8,
    width: 1,
    '&.MuiSlider-markActive': {
      opacity: 1,
      backgroundColor: 'currentColor'
    }
  }
}))

export const SettingsSlider = (props: any) => (
  <div style={{ flexGrow: 1 }}>
    <SettingsStylesSlider {...props} />
  </div>
)

export const SettingsSwitch = styled(Switch)(({ theme }: any) => ({
  width: 50,
  height: 26,
  padding: 0,
  '& .MuiSwitch-switchBase': {
    padding: 0,
    margin: 2,
    transitionDuration: '300ms',
    '&.Mui-checked': {
      transform: 'translateX(24px)',
      color: '#fff',
      '& + .MuiSwitch-track': {
        backgroundColor: theme.palette.primary,
        opacity: 1,
        border: 0
      },
      '&.Mui-disabled + .MuiSwitch-track': {
        opacity: 0.5
      }
    },
    '&.Mui-focusVisible .MuiSwitch-thumb': {
      color: '#33cf4d',
      border: '6px solid #fff'
    },
    '&.Mui-disabled .MuiSwitch-thumb': {
      color:
        theme.palette.mode === 'light'
          ? theme.palette.grey[100]
          : theme.palette.grey[600]
    },
    '&.Mui-disabled + .MuiSwitch-track': {
      opacity: theme.palette.mode === 'light' ? 0.7 : 0.3
    }
  },
  '& .MuiSwitch-thumb': {
    boxSizing: 'border-box',
    width: 22,
    height: 22
  },
  '& .MuiSwitch-track': {
    borderRadius: 26 / 2,
    backgroundColor: theme.palette.mode === 'light' ? '#E9E9EA' : '#39393D',
    opacity: 1,
    transition: theme.transitions.create(['background-color'], {
      duration: 500
    })
  }
}))

export const SettingsButton = (props: any) => {
  const classes = useStyles()
  return <Button size="small" className={classes.actionButton} {...props} />
}

export const SettingsRow = ({
  step,
  title,
  checked,
  onChange,
  children,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
  direct,
  // eslint-disable-next-line @typescript-eslint/no-unused-vars, no-unused-vars
  value,
  style,
  disabled
}: {
  step?: string
  title: string
  value?: any
  checked?: boolean
  direct?: boolean
  onChange?: () => void
  children?: any
  style?: any
  disabled?: boolean
}) => {
  const classes = useStyles()
  const theme = useTheme()
  return (
    <div
      className={`${classes.settingsRow} step-settings-${step} `}
      style={{
        ...style,
        color: disabled
          ? theme.palette.text.disabled
          : theme.palette.text.primary
      }}
    >
      <label>{title}</label>
      <div
        style={{
          display: 'flex',
          color: disabled ? '#000' : '#7b7a7c',
          flexGrow: 1,
          justifyContent: 'flex-end',
          textAlign: 'right'
        }}
      >
        {
          // ios ? (
          //   children ? (
          //     value
          //   ) : direct ? (
          //     <SettingsSwitch checked={checked} onChange={onChange} />
          //   ) : null
          // ) :
          children ||
            (title === 'Beta Mode' ? (
              <Tooltip title="AlphaMode: Smartbar -> HackedByBlade! -> OK -> BladeAlpha">
                <SettingsSwitch
                  disabled={disabled}
                  checked={checked}
                  onChange={onChange}
                />
              </Tooltip>
            ) : (
              <SettingsSwitch
                disabled={disabled}
                checked={checked}
                onChange={onChange}
              />
            ))
        }
        {/* {ios && !direct && <ChevronRight sx={{ ml: 1, color: '#57565a' }} />} */}
      </div>
    </div>
  )
}

SettingsRow.defaultProps = {
  step: 'x',
  children: null,
  value: null,
  checked: false,
  direct: false,
  onChange: null,
  style: null,
  disabled: false
}

export const SettingsAccordion = ({
  title,
  accId,
  children,
  icon = ''
}: {
  title: string
  accId: string
  children: any
  // eslint-disable-next-line react/require-default-props
  icon?: string
}) => {
  const settingsExpanded = useStore((state) => state.ui.settingsExpanded)
  const setSettingsExpanded = useStore((state) => state.ui.setSettingsExpanded)
  const handleExpanded = (panel: any, _event: any, isExpanded: any) => {
    setSettingsExpanded(isExpanded ? panel : false)
  }
  return (
    <Accordion
      onDoubleClick={() => setSettingsExpanded('all')}
      expanded={
        settingsExpanded === 'all' || settingsExpanded === `panel${accId}`
      }
      onChange={(event, isExpanded) =>
        handleExpanded(`panel${accId}`, event, isExpanded)
      }
    >
      <AccordionSummary
        expandIcon={<ExpandMore />}
        aria-controls={`panel${accId}-content`}
        id={`panel${accId}-header`}
      >
        {icon && icon !== '' ? (
          <BladeIcon name={icon} style={{ marginRight: '0.75rem' }} />
        ) : (
          <></>
        )}
        <Typography>{title}</Typography>
      </AccordionSummary>
      <AccordionDetails>{children}</AccordionDetails>
    </Accordion>
  )
}
