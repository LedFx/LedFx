import { Button, useTheme, Stack } from '@mui/material'
import { GitHub } from '@mui/icons-material'

import BladeFrame from '../../components/SchemaForm/components/BladeFrame'

const DbLinks = () => {
  const theme = useTheme()

  return (
    <BladeFrame
      labelStyle={{
        background: theme.palette.background.default,
        color: theme.palette.primary.main
      }}
      style={{
        borderColor: theme.palette.primary.main,
        padding: 20,
        minWidth: 280
        // color: theme.palette.text.disabled,
      }}
      title="Links"
    >
      <Stack width="100%">
        <Button
          onClick={() =>
            window.open(
              'https://github.com/LedFx/LedFx',
              '_blank',
              'noopener,noreferrer'
            )
          }
          variant="text"
          startIcon={<GitHub />}
          size="large"
          sx={{
            textTransform: 'none',
            justifyContent: 'flex-start',
            '& .MuiButton-startIcon': {
              mr: 3
            }
          }}
        >
          LedFx
        </Button>
      </Stack>
    </BladeFrame>
  )
}

export default DbLinks
