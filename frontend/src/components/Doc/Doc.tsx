/* eslint-disable @typescript-eslint/indent */
/* eslint-disable react/require-default-props */
/* eslint-disable @typescript-eslint/no-empty-function */
/* eslint-disable import/no-unresolved */
import React from 'react'
import Button from '@mui/material/Button'
import Dialog from '@mui/material/Dialog'
import AppBar from '@mui/material/AppBar'
import Toolbar from '@mui/material/Toolbar'
import Typography from '@mui/material/Typography'
import Slide from '@mui/material/Slide'
import NavigateBeforeIcon from '@mui/icons-material/NavigateBefore'
import { ListItemIcon, MenuItem, useTheme } from '@mui/material'
import { MenuBook } from '@mui/icons-material'
// import { API } from '@stoplight/elements';
import { TransitionProps } from '@mui/material/transitions'
import '@stoplight/elements/styles.min.css'
// import configApiYaml from './configApiYaml';

const Transition = React.forwardRef<unknown, TransitionProps>(
  function Transition(props, ref) {
    return <Slide direction="up" ref={ref} {...(props as any)} />
  }
)

type Props = {
  _?: never
  className?: string | undefined
  onClick?: any
  children?: any
}

const MuiMenuItem = React.forwardRef<HTMLLIElement, Props>((props, ref) => {
  const { children } = props
  return (
    <MenuItem ref={ref} {...props}>
      {children}
    </MenuItem>
  )
})

function FrameWrapper() {
  const ref = React.useRef<any>()
  const [height, setHeight] = React.useState('0px')
  const onLoad = () => {
    setHeight(`${ref.current.contentWindow.document.body.scrollHeight}px`)
  }
  return (
    <iframe
      title="docs"
      ref={ref}
      onLoad={onLoad}
      id="myFrame"
      src="https://yeonv.github.io/LedFx-Frontend-v2/docs/"
      width="100%"
      height={height}
      scrolling="no"
      frameBorder="0"
      style={{
        maxWidth: 640,
        width: '100%',
        overflow: 'auto'
      }}
    />
  )
}

export default function Doc({
  icon = <MenuBook />,
  startIcon,
  label = '',
  type,
  className,
  color = 'inherit',
  variant = 'contained',
  onClick = () => {},
  innerKey
}: any) {
  const [open, setOpen] = React.useState(false)
  const theme = useTheme()
  const handleClickOpen = () => {
    setOpen(true)
  }

  const handleClose = () => {
    setOpen(false)
  }

  return (
    <>
      {type === 'menuItem' ? (
        <MuiMenuItem
          key={innerKey}
          className={className}
          onClick={(e: any) => {
            e.preventDefault()
            onClick(e)
            handleClickOpen()
          }}
        >
          <ListItemIcon>{icon}</ListItemIcon>
          {label}
        </MuiMenuItem>
      ) : (
        <Button
          variant={variant}
          startIcon={startIcon}
          color={color}
          onClick={(e: any) => {
            onClick(e)
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
        <AppBar
          enableColorOnDark
          sx={{
            position: 'relative',
            marginBottom: '1rem',
            background: theme.palette.background.default,
            color: theme.palette.text.primary
          }}
        >
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
            <Typography
              variant="h6"
              sx={{
                marginLeft: theme.spacing(2),
                flex: 1
              }}
            >
              Documentation
            </Typography>
          </Toolbar>
        </AppBar>
        {FrameWrapper()}
        {/* <API apiDescriptionUrl={"https://raw.githubusercontent.com/LedFx/ledfx_rewrite/main/api/openapi.yml"} /> */}
        {/* <API
          apiDescriptionDocument={configApiYaml}
          basePath="LedFx-Frontend-v2/docs"
          logo="https://github.com/LedFx/LedFx/raw/main/icons/discord.png"
          router='memory'
        /> */}
      </Dialog>
    </>
  )
}
