import { useState, useRef, useEffect } from 'react'
import Popper from '@mui/material/Popper'
import ReactGPicker from 'react-gcolor-picker'
import { TextField, Button, useTheme } from '@mui/material'
import { Add } from '@mui/icons-material'
import useClickOutside from '../../../../utils/useClickOutside'
import Popover from '../../../Popover/Popover'
import DeleteColorsDialog from '../../../Dialogs/DeleteColors'
import useStyles from './GradientPicker.styles'
import {
  GradientPickerDefaultProps,
  GradientPickerProps
} from './GradientPicker.props'

const GradientPicker = ({
  pickerBgColor,
  title,
  index,
  isGradient = false,
  wrapperStyle,
  colors,
  handleAddGradient,
  sendColorToVirtuals,
  showHex = false
}: GradientPickerProps) => {
  const classes = useStyles()
  const theme = useTheme()
  const popover = useRef(null)
  const [anchorEl, setAnchorEl] = useState(null)
  const [name, setName] = useState('')
  const [dialogOpen, setDialogOpen] = useState(false)
  const [pickerBgColorInt, setPickerBgColorInt] = useState(pickerBgColor)

  const defaultColors: any = {}
  Object.entries(colors.gradients.builtin).forEach(([k, g]) => {
    defaultColors[k] = g
  })
  Object.entries(colors.gradients.user).forEach(([k, g]) => {
    defaultColors[k] = g
  })
  Object.entries(colors.colors.builtin).forEach(([k, g]) => {
    defaultColors[k] = g
  })
  Object.entries(colors.colors.user).forEach(([k, g]) => {
    defaultColors[k] = g
  })

  const handleClick = (event: any) => {
    setAnchorEl(anchorEl ? null : event.currentTarget)
  }

  const handleClose = () => {
    setAnchorEl(null)
  }

  useClickOutside(popover, handleClose)

  const handleDeleteDialog = () => {
    setAnchorEl(null)
    setDialogOpen(true)
  }
  const open = Boolean(anchorEl)
  const id = open ? 'simple-popper' : undefined

  useEffect(() => {
    setPickerBgColorInt(pickerBgColor)
  }, [pickerBgColor, setPickerBgColorInt])

  useEffect(() => {
    setPickerBgColorInt(pickerBgColor)
  }, [pickerBgColor, setPickerBgColorInt])

  return (
    <div
      className={`${classes.wrapper} step-effect-${index} gradient-picker`}
      style={{
        borderColor: theme.palette.divider,
        minWidth: 'unset',
        ...(wrapperStyle as any)
      }}
      // style={{
      //   ...wrapperStyle,
      //   '& > label': {
      //     backgroundColor: theme.palette.background.paper,
      //   },
      // }}
    >
      <label
        className="MuiFormLabel-root"
        style={{ background: theme.palette.background.paper }}
      >
        {title &&
          title
            .replaceAll('_', ' ')
            .replaceAll('background', 'bg')
            .replaceAll('name', '')}
      </label>
      {/* eslint-disable-next-line */}
      <div
        className={classes.picker}
        style={{ background: pickerBgColorInt }}
        aria-describedby={id}
        onClick={handleClick}
      />

      <Popper id={id} open={open} anchorEl={anchorEl} ref={popover && popover}>
        <div
          className={`${classes.paper} gradient-picker ${
            showHex ? 'show_hex' : ''
          }`}
          style={{
            padding: theme.spacing(1),
            backgroundColor: theme.palette.background.paper
            // '& .popup_tabs-header-label-active': {
            //   color: theme.palette.text.primary,
            // },
            // '& .popup_tabs-header-label': {
            //   color: theme.palette.text.disabled,
            //   '&.popup_tabs-header-label-active': {
            //     color: theme.palette.text.primary,
            //   },
            // },
          }}
        >
          <ReactGPicker
            colorBoardHeight={150}
            debounce
            debounceMS={300}
            format="hex"
            gradient={isGradient}
            solid
            onChange={(c) => {
              setPickerBgColorInt(c)
              return sendColorToVirtuals(c)
            }}
            popupWidth={288}
            showAlpha={false}
            value={pickerBgColorInt}
            defaultColors={Object.values(defaultColors)}
          />
          <div
            style={{
              marginTop: 2.5,
              width: '100%',
              display: 'flex',
              justifyContent: 'flex-end'
            }}
          >
            <Button
              style={{
                width: 69,
                height: 30,
                borderRadius: 4,
                border: '1px solid #999',
                display: 'flex',
                justifyContent: 'center',
                alignItems: 'center',
                fontSize: 24,
                marginRight: 16,
                cursor: 'pointer'
              }}
              onClick={() => handleDeleteDialog()}
              disabled={
                colors &&
                colors.length &&
                colors.colors?.length &&
                colors.gradients?.length &&
                !(Object.keys(colors.colors.user)?.length > 0) &&
                !(Object.keys(colors.gradients.user)?.length > 0)
              }
            >
              -
            </Button>
            <Popover
              className={classes.addButton}
              popoverStyle={{ padding: '0.5rem' }}
              color="primary"
              content={
                <TextField
                  autoFocus
                  onClick={(e) => e.stopPropagation()}
                  onKeyDown={(e: any) =>
                    e.key === 'Enter' && handleAddGradient(name)
                  }
                  error={
                    colors?.length &&
                    colors.colors?.length &&
                    colors.gradients?.length &&
                    (Object.keys(colors.colors).indexOf(name) > -1 ||
                      Object.values(colors.colors).filter(
                        (p) => p === pickerBgColorInt
                      )?.length > 0 ||
                      Object.keys(colors.gradients).indexOf(name) > -1 ||
                      Object.values(colors.gradients).filter(
                        (p) => p === pickerBgColorInt
                      ).length > 0)
                  }
                  size="small"
                  id="gradientNameInput"
                  label="Enter name to save as..."
                  style={{ marginRight: '1rem', flex: 1 }}
                  value={name}
                  onChange={(e) => {
                    setName(e.target.value)
                  }}
                />
              }
              confirmDisabled={name.length === 0}
              onConfirm={() => handleAddGradient(name)}
              startIcon=""
              size="medium"
              icon={<Add />}
            />
          </div>
        </div>
      </Popper>
      <DeleteColorsDialog
        setDialogOpen={setDialogOpen}
        dialogOpen={dialogOpen}
      />
    </div>
  )
}

GradientPicker.defaultProps = GradientPickerDefaultProps

export default GradientPicker
