import { Stack, useTheme } from '@mui/material'

const PadData = ({ label, value }: any) => {
  const theme = useTheme()
  return (
    <Stack
      direction="column"
      sx={{
        '&>span:first-of-type': {
          color: '#999',
          mr: 2,
          textTransform: 'uppercase',
          fontSize: '0.8rem'
        }
      }}
    >
      <span>{label}</span>
      <span
        style={{
          color:
            parseInt(value, 10) === -1 || parseInt(value, 10) === 1
              ? theme.palette.primary.main
              : 'inherit'
        }}
      >
        {String(value)}
      </span>
    </Stack>
  )
}

export default PadData
