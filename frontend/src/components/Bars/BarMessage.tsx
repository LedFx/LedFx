import { Icon, IconButton, Snackbar, Alert, AlertColor } from '@mui/material'
import { useEffect } from 'react'
import useStore from '../../store/useStore'

const MessageBar = () => {
  const { message, messageType, isOpen } = useStore(
    (state) => state.ui.snackbar
  )
  const clearSnackbar = useStore((state) => state.ui?.clearSnackbar)
  const setCurrentVirtual = useStore((state) => state.setCurrentVirtual)

  function handleClose() {
    clearSnackbar?.()
  }

  useEffect(() => {
    if (typeof message === 'string' && message.startsWith('Created Virtual ')) {
      setCurrentVirtual(message.replace('Created Virtual ', ''))
    }
  }, [message])

  return (
    <Snackbar
      anchorOrigin={{
        vertical: 'bottom',
        horizontal: 'center'
      }}
      open={isOpen}
      autoHideDuration={2000 + (message.length || 0) * 60}
      onClose={() => handleClose()}
      aria-describedby="client-snackbar"
      action={[
        <IconButton
          key="close"
          aria-label="close"
          color="inherit"
          onClick={() => handleClose()}
        >
          <Icon>close</Icon>
        </IconButton>
      ]}
    >
      <Alert
        elevation={6}
        variant="filled"
        severity={
          message.includes('[ERROR') ? 'error' : (messageType as AlertColor)
        }
        sx={{
          whiteSpace: 'pre-line',
          width: message.includes('[ERROR') ? 'min(80vw, 720px)' : 'auto'
        }}
      >
        {message.replace(/\[ERROR|\[Errno/g, (match, offset) =>
          offset > 0 ? `\n${match}` : match
        )}
        {/* <div
          dangerouslySetInnerHTML={{
            __html: message.split('[ERROR').join('<br />[ERROR')
          }}
        /> */}
      </Alert>
    </Snackbar>
  )
}

export default MessageBar
