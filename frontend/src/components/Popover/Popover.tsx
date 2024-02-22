import { ReactElement, useState } from 'react'
import {
  Typography,
  Button,
  MenuItem,
  ListItemIcon,
  Popover as PopoverOriginal,
  useTheme,
  Fab,
  IconButton
} from '@mui/material'
import { Delete, Close, Check } from '@mui/icons-material'
import { useLongPress } from 'use-long-press'
import { PopoverProps, PopoverDefaults } from './Popover.interface'

const Popover = ({
  onConfirm,
  onCancel,
  confirmDisabled,
  confirmContent,
  onSingleClick,
  onDoubleClick,
  openOnDoubleClick = false,
  openOnLongPress = false,
  noIcon = false,
  disabled = false,
  variant = 'contained',
  color = 'secondary',
  vertical = 'center',
  horizontal = 'left',
  size = 'small',
  text = 'Are you sure?',
  label = undefined,
  anchorOrigin,
  transformOrigin,
  startIcon,
  icon = <Delete />,
  content,
  footer,
  className,
  style = {},
  sx,
  popoverStyle,
  wrapperStyle,
  type = 'button',
  children
}: PopoverProps): ReactElement<any, any> => {
  const theme = useTheme()
  const [anchorEl, setAnchorEl] = useState(null)
  const openPopover = (event: any) => {
    // eslint-disable-next-line
    setAnchorEl(() => event.currentTarget || event.target)
  }
  const handleClose = () => {
    setAnchorEl(null)
  }
  const longPress = useLongPress((e) => openPopover(e), {
    onCancel: (e) => {
      if (onSingleClick) onSingleClick(e)
    },
    threshold: 1000,
    captureEvent: true
  })
  const open = Boolean(anchorEl)
  const id = open ? 'simple-popover' : undefined

  return (
    <div style={{ display: 'initial', margin: 0, ...wrapperStyle }}>
      {type === 'menuItem' ? (
        <MenuItem
          className={className}
          onClick={(e) => {
            e.preventDefault()
            if (onSingleClick) onSingleClick(e)
            openPopover(e)
          }}
        >
          <ListItemIcon>{icon}</ListItemIcon>
          {label}
        </MenuItem>
      ) : openOnLongPress ? (
        type === 'button' ? (
          <Button
            aria-describedby={id}
            variant={variant}
            color={color}
            size={size}
            className={className}
            style={style}
            startIcon={!noIcon && startIcon}
            disabled={disabled}
            // eslint-disable-next-line
                {...longPress}
          >
            {label}
            {!startIcon && !noIcon && icon}
          </Button>
        ) : (
          <Fab
            aria-label="clear-data"
            {...longPress}
            disabled={disabled}
            style={{
              margin: '8px',
              ...style
            }}
            sx={{
              bgcolor: theme.palette.primary.main,
              '&:hover': {
                bgcolor: theme.palette.primary.light
              }
            }}
          >
            {!startIcon && !noIcon && icon}
          </Fab>
        )
      ) : type === 'button' ? (
        <Button
          aria-describedby={id}
          variant={variant}
          color={color}
          onClick={(e) => {
            e.preventDefault()
            if (!openOnDoubleClick) openPopover(e)
            if (onSingleClick) onSingleClick(e)
          }}
          size={size}
          className={className}
          style={style}
          startIcon={!noIcon && startIcon}
          disabled={disabled}
          onDoubleClick={(e) => {
            e.preventDefault()
            if (openOnDoubleClick) openPopover(e)
            if (onDoubleClick) onDoubleClick(e)
          }}
        >
          {label}
          {!startIcon && !noIcon && icon}
          {children}
        </Button>
      ) : type === 'iconbutton' ? (
        <IconButton
          color={color}
          style={style}
          onClick={(e) => openPopover(e)}
          disabled={disabled}
        >
          {!startIcon && !noIcon && icon}
        </IconButton>
      ) : (
        <Fab
          aria-label="clear-data"
          onClick={(e) => {
            e.preventDefault()
            if (!openOnDoubleClick) openPopover(e)
            if (onSingleClick) onSingleClick(e)
          }}
          onDoubleClick={(e) => {
            e.preventDefault()
            if (openOnDoubleClick) openPopover(e)
            if (onDoubleClick) onDoubleClick(e)
          }}
          disabled={disabled}
          style={{
            margin: '8px'
          }}
          sx={{
            bgcolor: theme.palette.primary.main,
            '&:hover': {
              bgcolor: theme.palette.primary.light
            },
            ...sx
          }}
        >
          {!startIcon && !noIcon && icon}
          {children}
        </Fab>
      )}
      <PopoverOriginal
        id={id}
        open={open}
        anchorEl={anchorEl}
        onClose={handleClose}
        anchorOrigin={
          anchorOrigin || {
            vertical,
            horizontal
          }
        }
        transformOrigin={
          transformOrigin || {
            vertical,
            horizontal: horizontal === 'center' ? 'center' : 'right'
          }
        }
      >
        <div style={{ display: 'flex', ...popoverStyle }}>
          {content || (
            <Typography sx={{ padding: theme.spacing(2) }}>{text}</Typography>
          )}
          <Button
            disabled={confirmDisabled}
            aria-describedby={id}
            variant="contained"
            color="primary"
            onClick={(e) => {
              e.preventDefault()
              if (onConfirm) onConfirm(e)
              setAnchorEl(null)
            }}
          >
            {confirmContent || <Check />}
          </Button>
          <Button
            aria-describedby={id}
            color="primary"
            onClick={(e) => {
              e.preventDefault()
              if (onCancel) onCancel(e)
              setAnchorEl(null)
            }}
          >
            <Close />
          </Button>
        </div>
        {footer}
      </PopoverOriginal>
    </div>
  )
}

Popover.defaultProps = PopoverDefaults

export default Popover
