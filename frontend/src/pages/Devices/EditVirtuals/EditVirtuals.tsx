/* eslint-disable react/prop-types */
/* eslint-disable react/require-default-props */
/* eslint-disable @typescript-eslint/no-empty-function */
import React, { useEffect, useState } from 'react'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import AppBar from '@mui/material/AppBar'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore'

import {
  ListItemIcon,
  MenuItem,
  Slide,
  IconButton,
  ToggleButtonGroup,
  ToggleButton
} from '@mui/material'
import {
  GridOn,
  Settings,
  Visibility,
  VisibilityOff
} from '@mui/icons-material'
import { TransitionProps } from '@mui/material/transitions'
import { getOverlapping } from '../../../utils/helpers'
import useStore from '../../../store/useStore'

import AddSegmentDialog from '../../../components/Dialogs/_AddSegmentDialog'
import Segment from './Segment'

import useEditVirtualsStyles from './EditVirtuals.styles'
import EditMatrix from './EditMatrix/M'
import BladeIcon from '../../../components/Icons/BladeIcon/BladeIcon'

const Transition = React.forwardRef<unknown, TransitionProps>(
  function Transition(props, ref) {
    return <Slide direction="up" ref={ref} {...(props as any)} />
  }
)
type Props = {
  _?: never
  children?: any
  className?: string | undefined
  onClick?: any
}

const MuiMenuItem = React.forwardRef<HTMLLIElement, Props>((props, ref) => {
  const { children } = props
  return (
    <MenuItem ref={ref} {...props}>
      {children}
    </MenuItem>
  )
})

export default function EditVirtuals({
  virtId,
  icon = <Settings />,
  startIcon,
  label = '',
  type,
  className,
  color = 'inherit',
  variant = 'contained',
  onClick = () => {},
  innerKey
}: any) {
  const [matrix, setMatrix] = useState(false)
  const features = useStore((state) => state.features)
  const currentVirtual = useStore((state) => state.currentVirtual)
  const setCurrentVirtual = useStore((state) => state.setCurrentVirtual)
  const calibrationMode = useStore((state) => state.calibrationMode)
  const classes = useEditVirtualsStyles()
  const showSnackbar = useStore((state) => state.ui.showSnackbar)
  const getDevices = useStore((state) => state.getDevices)
  const virtuals = useStore((state) => state.virtuals)
  // const editVirtual = useStore((state) => state.dialogs.editVirtual);
  const setDialogOpenEditVirtual = useStore(
    (state) => state.setDialogOpenEditVirtual
  )
  const activeSegment = useStore((state) => state.activeSegment)
  const highlightSegment = useStore((state) => state.highlightSegment)

  const virtual = virtuals[currentVirtual || virtId]
  const [open, setOpen] = React.useState(!!currentVirtual || false)
  const [calib, setCalib] = React.useState(true)

  const handleClickOpen = () => {
    setOpen(true)
  }

  const handleClose = () => {
    const output = getOverlapping(virtual.segments)
    const overlap = Object.keys(output).find((k) => output[k].overlap)
    if (overlap) {
      showSnackbar(
        'warning',
        `Overlapping in ${overlap} detected! Please Check your config`
      )
    } else {
      setOpen(false)
      setDialogOpenEditVirtual(false)
      setCurrentVirtual(null)
      onClick()
    }
  }

  useEffect(() => {
    getDevices()
  }, [getDevices])

  useEffect(() => {
    if (currentVirtual && type === 'hidden') {
      setOpen(true)
    }
  }, [currentVirtual])

  useEffect(() => {
    if (virtual?.id && open) calibrationMode(virtual?.id, 'on')

    return () => {
      if (virtual?.id && open) calibrationMode(virtual?.id, 'off')
    }
  }, [virtual?.id, open])

  // useEffect(() => {
  //   const unloadCallback = (event: any) => {
  //     event.preventDefault()
  //     if (virtual?.id) calibrationMode(virtual?.id, 'off')
  //     return ''
  //   }

  //   window.addEventListener('beforeunload', unloadCallback)
  //   return () => window.removeEventListener('beforeunload', unloadCallback)
  // }, [])

  return virtual && virtual.config ? (
    <>
      {type === 'menuItem' ? (
        <MuiMenuItem
          key={innerKey}
          className={className}
          onClick={(e: any) => {
            e.preventDefault()
            handleClickOpen()
          }}
        >
          <ListItemIcon>{icon}</ListItemIcon>
          {label}
        </MuiMenuItem>
      ) : type === 'hidden' ? null : (
        <Button
          variant={variant}
          startIcon={startIcon}
          color={color}
          onClick={() => {
            // onClick(e);
            handleClickOpen()
          }}
          size="small"
          className={className}
        >
          {label}
          {!startIcon && icon}
        </Button>
      )}
      <Dialog
        fullScreen
        open={open}
        onClose={handleClose}
        TransitionComponent={Transition}
      >
        <AppBar enableColorOnDark className={classes.appBar}>
          <Toolbar>
            <Button
              autoFocus
              color="primary"
              variant="contained"
              startIcon={<NavigateBeforeIcon />}
              onClick={handleClose}
              style={{ marginRight: '1rem' }}
            >
              back
            </Button>
            {features.matrix && (
              <ToggleButtonGroup
                value={matrix}
                style={{ marginRight: '1rem' }}
                size="small"
                exclusive
                onChange={() => setMatrix(!matrix)}
                aria-label="mode"
              >
                <ToggleButton value={false}>
                  <BladeIcon name="mdi:led-strip" />
                </ToggleButton>
                <ToggleButton value>
                  <GridOn />
                </ToggleButton>
                {/* <ToggleButton disabled value="3d">
                <BladeIcon name="mdi:cube-outline" />
              </ToggleButton> */}
              </ToggleButtonGroup>
            )}

            {/* {matrix ? '2D matrix' : '1D Strip'} */}
            <Typography variant="h6" className={classes.title}>
              {virtual.config.name}{' '}
            </Typography>
            <IconButton
              onClick={() => {
                calibrationMode(virtual?.id, calib ? 'off' : 'on')
                if (!calib && virtual.segments[activeSegment])
                  highlightSegment(
                    virtual.id,
                    virtual.segments[activeSegment][0],
                    virtual.segments[activeSegment][1],
                    virtual.segments[activeSegment][2],
                    virtual.segments[activeSegment][3]
                  )
                setCalib(!calib)
              }}
            >
              {calib ? <Visibility /> : <VisibilityOff />}
            </IconButton>
          </Toolbar>
        </AppBar>
        {matrix ? (
          <EditMatrix virtual={virtual} />
        ) : (
          <>
            <div className={classes.segmentTitle}>
              <Typography variant="caption">Segments-Settings</Typography>
            </div>
            {virtual.segments?.length > 0 &&
              virtual.segments.map((s: any, i: number) => (
                <Segment
                  s={s}
                  i={i}
                  key={i}
                  virtual={virtual}
                  segments={virtual.segments}
                  calib={calib}
                />
              ))}
            <div className={classes.segmentButtonWrapper}>
              <AddSegmentDialog virtual={virtual} />
            </div>
          </>
        )}
      </Dialog>
    </>
  ) : null
}
